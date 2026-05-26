/**
 * app.js — Football Chronicle frontend
 *
 * Calls the Flask API and renders state dicts into the DOM.
 * No game logic lives here — only rendering and HTTP calls.
 *
 * STRUCTURE
 * =========
 * advance()          — POST /api/advance, then render()
 * choose(index)      — POST /api/choose, then render()
 * render(state)      — dispatch to the right renderer by state.type
 * renderMatchday()   — results + standings + notifications
 * renderBlockingEvent()
 * renderSeasonEnd()
 * renderBetweenSeasons()
 * renderGameOver()
 *
 * Helpers:
 * api(method, path, body)  — fetch wrapper
 * setStatus(msg)           — update footer status line
 * refreshNews()            — pull latest from /api/news
 * refreshInbox()           — pull latest from /api/inbox
 */

const API = 'http://localhost:5000'

// API wrapper

async function api(method, path, body = null) {
    const opts = {
        method,
        headers: {"Content-Type": "application/json"},
    };
    if (body !== null) opts.body = JSON.stringify(body);
    const res = await fetch(`${API}${path}`, opts);
    return res.json();
}

// Main actions

async function advance() {
    setStatus("Advancing...");
    disable(true);
    try {
        const state = await api("POST", "/api/advance");
        render(state);
        await refreshNews();
        await refreshInbox();
    }   catch (e) {
        setStatus(`Error: ${e.message}`);
    }   finally {
        disable(false);
    }
}

async function choose(index) {
    setStatus("Resolving...");
    disable(true);
    try {
        const state = await api("POST", "/api/choose", {index});
        render(state);
        await refreshNews();
        await refreshInbox();
    }   catch (e) {
        setStatus(`Error: ${e.message}`);
    }   finally {
        disable(false);
    }
}

// Central renderer

function render(state) {
    // Hide all panels first
    hide("panel-event");
    hide("panel-season-end");

    const type = state.type;

    if (type === "matchday")                renderMatchday(state);
    else if (type === "blocking-event")     renderBlockingEvent(state);
    else if (type === "season-end")         renderSeasonEnd(state);
    else if (type === "between-seasons")    renderBetweenSeasons(state);
    else if (type === "game-over")          renderGameOver(state);
    else if (type === "not-started")        setStatus("Ready. Press Advance to begin.");
    else if (type === "error")              setStatus(`Error: ${state.message}`);
}

// Matchday renderer

function renderMatchday(state) {
    // Update masthead
    setText("meta-season", state.season);
    setText("meta-matchday", `Matchday ${state.matchday_num}`);
    setText("meta-date", formatDate(state.date));

    // Update standings
    renderStandings(state.standings);

    // Add matchday block to the results feed
    hide("feed-placeholder");
    const feed = document.getElementById("results-feed");

    const block = document.createElement("div");
    block.className = "matchday-block";
    block.innerHTML = `
        <div class="matchday-heading">
            <span>${state.competition} - Matchday ${state.matchday_num}</span>
            <span class="match-date">${formatDate(state.date)}</span>
        </div>
        ${state.results.map(renderResultCard).join("")}
    `;

    // Prepend so newest results are on top
    const placeholder = document.getElementById("feed-placeholder");
    feed.insertBefore(block, placeholder.nextSibling || null);

    // Right column: injuries and suspensions
    renderNotifications(state.new_injuries || [], state.newly_suspended || []);

    // Footer
    setStatus(`Matchday ${state.matchday_num} complete.`);
    const next = state.next_event_date
        ? `Next: ${formatDate(state.next_event_date)}`
        : "Season ending soon...";
    setText("footer-next", next);
}

function renderResultCard(result) {
    const hg = result.home_goals;
    const ag = result.away_goals;

    const homeGoals = goalScorers(result.events, result.home_team);
    const awayGoals = goalScorers(result.events, result.away_team);

    return `
        <div class="result-card">
            <div class="result-team-home">
                <div>${result.home_team}</div>
                ${homeGoals ? `<div class="result-scorers">${homeGoals}</div>` : ""}
            </div>
            <div class="result-score">${hg} - ${ag}</div>
            <div class="result-team-away">
                <div>${result.away_team}</div>
                ${awayGoals ? `<div class="result-scorers">${awayGoals}</div>` : ""}
            </div>
        </div>
    `;
}

function goalScorers(events, teamName) {
    if (!events) return "";
    return events
        .filter(e => e.type === "goal" && e.team === teamName)
        .map(e => {
            const assist = e.assister ? ` (${e.assister})` : "";
            return `${e.player}${assist} (${e.minute})`;
        })
        .join(" · ");
}

// Standings renderer

function renderStandings(standings) {
    const tbody = document.getElementById("standings-body");
    if (!standings || standings.length === 0) return;

    tbody.innerHTML = standings.map((row, i) => {
        const cls = i < 1 ? "top-3 promoted" : i < 3 ? "top-3" : "";
        const name = row.team.length > 16
            ? row.team.slice(0, 15) + "..."
            : row.team;
        return `
            <tr class="${cls}">
                <td>${i + 1}</td>
                <td class="team-col" title="${row.team}">${name}</td>
                <td>${row.played}</td>
                <td>${row.wins}</td>
                <td>${row.draws}</td>
                <td>${row.losses}</td>
                <td>${row.goal_difference > 0 ? "+" : ""}${row.goal_difference}</td>
                <td>${row.points}</td>
            </tr>
        `;
    }).join("");
}

// Blocking event renderer

function renderBlockingEvent(state) {
    show("panel-event");
    hide("feed-placeholder");

    setText("event-category", state.category.replace("_", " ").toUpperCase());
    setText("event-title", state.title);
    setText("event-description", state.description);

    const choicesEl = document.getElementById("event-choices");
    choicesEl.innerHTML = "";

    if (state.choices && state.choices.length > 0) {
        state.choices.forEach(c => {
            const btn = document.createElement("button");
            btn.className = "choice-btn";
            btn.textContent = c.text;
            btn.dataset.index = c.index + 1;
            btn.onclick = () => choose(c.index);
            choicesEl.appendChild(btn);
        });
        setStatus(state.title);
        setText("footer-next", "Make your choice to continue.");
    }   else {
        // Acknowledgement only event
        const btn = document.createElement("button");
        btn.className = "advance-btn";
        btn.textContent = "Acknowledge";
        btn.onclick = () => choose(0);
        choicesEl.appendChild(btn);
        setStatus(state.title);
    }
}

// Season end renderer

function renderSeasonEnd(state) {
    show("panel-season-end");
    hide("feed-placeholder");

    // Champion declaration
    document.getElementById("champion-declaration").innerHTML = `
        Champions of the ${state.season} season:<br>
        <strong>${state.champion}</strong>
    `;

    // Stats grid
    const grid = document.getElementById(season-stats-grid);
    grid.innerHTML = `
        ${statBlock("Top Scorers", state.top_scorers, p =>
            `${p.name} <span class="stat-val">${p.goals}</span>`)}
        ${statBlock("Top Assisters", state.top_assisters, p =>
            `${p.name} <span class="stat-val">${p.assists}</span>`)}
        ${statBlock("Top Rated", state.top_rated, p =>
            `${p.name} <span class="stat-val">${p.avg_rating}</span>`)}
        ${statBlock("Top Clean Sheets", state.top_clean_sheets, p =>
            `${p.name} <span class="stat-val">${p.clean_sheets}</span>`)}
    `;

    // Final standings
    renderStandings(state.final_standings);

    // Wire up the next season button
    document.getElementById("btn-next-season").onclick = advance;

    setText("meta-season", state.season);
    setText("meta-matchday", "Season Complete");
    setStatus(`Season ${state.season} complete.`);
    setText("footer-next", "");
}

function statBlock(title, players, rowFn) {
    if (!players || players.length === 0) return "";
    const items = players.slice(0, 5).map(p =>
        `<li>${rowFn(p)}</li>`
    ).join("");
    return `
        <div class="stat-block">
            <h4>${title}</h4>
            <ol>${items}</ol>
        </div>
    `;
}

// Between seasons renderer

function renderBetweenSeasons(state) {
    hide("panel-season-end");

    // Inject a development log entry into the results feed
    hide("feed-placeholder");
    const feed = document.getElementById("results_feed");
    const log = state.development_log || [];

    if (log.length > 0) {
        const block = document.createElement("div");
        block.className = "matchday-block";
        const rows = log.slice(0, 15).map(e => {
            const arrow = e.direction === "up" ? "▲" : "▼";
            const color = e.direction === "up" ? "var(--accent)" : "var(--ink-light)";
            return `<div style="font-family: var(--mono); font-size: 0.7rem;
                    color: var(--ink-faded); padding: 0.15rem 0;
                    border-bottom: 1px dotted var(--rule-light)">
                <span style="color: ${color}; margin-right: 0.4rem">${arrow}</span>
                ${e.player} <span style="color: var(--ink-light)>(${e.team})</span>
                <span style="float: right; color: var(--ink-light)">
                    ${e.old_ca} → <strong style="color: var(--ink)">${e.new_ca}</strong>
                </span>
            </div>`;
        }).join("");

        block.innerHTML = `
            <div class="matchday-heading">
                <span>Player Development - ${state.completed_season}</span>
                <span class="match-date">${log.length} notable changes</span>
            </div>
            ${rows}
        `;
        feed.insertBefore(block, feed.firstChild);
    }

    setText("meta-season", state.next_season);
    setText("meta-matchday", "Pre-Season");
    setStatus(`${state.completed_season} complete. ${state.next_season} begins...`);
}

// Game over renderer

function renderGameOver(state) {
    hide("panel-season-end");
    hide("feed-placeholder");

    const feed = document.getElementById("results-feed");
    const block = document.createElement("div");
    block.className = "matchday_block";
    block.innerHTML = `
        <div class="matchday-heading">
            <span>Simulation Complete</span>
            <span class="match-date">${state.seasons_played} seasons</span>
        </div>
        <div style="text-align-center"; padding: 2rem; font-family: var(--fell);
            font-style: italic; color: var(--ink-faded); font-size: 1.1rem">
            The chronicle is complete. ${state.seasons_played} seasons of football
            have been recorded for posterity.
        </div>
    `;
    feed.insertBefore(block, feed.firstChild);

    document.getElementById("btn-advance").disabled = true;
    setStatus("Simulation complete.");
    setText("footer-next", "");
}

// Notifications (right column)

function renderNotifications(injuries, suspended) {
    const list = document.getElementById("notice-list");
    const items = [];

    injuries.forEach(inj => {
        items.push(`
            <li class="notice-item injury">
                <span class="notice-tag">Injury - ${inj.severity}</span>
                ${inj.player} ${inj.team} - ${inj.matches} match${inj.matches !== 1 ? "es" : ""} out
            </li>
        `);
    });

    suspended.forEach(sus => {
        items.push(`
            <li class="notice-item suspended">
                <span class="notice-tag">Suspension</span>
                ${s.player} ${s.team} - ${s.matches} match ban
            </li>
        `);
    });

    if (items.length === 0) {
        list.innerHTML = "<li class='empty-state'>No notices.</li>";
    } else {
        list.innerHTML = items.join("");
    }
}

// News feed (left column)

async function refreshNews() {
    try {
        const events = await pi("GET", "/api/news?limit=12&relevance=local");
        const list = document.getElementById("news-list");

        if (!events || events.length === 0) {
            list.innerHTML = "<li class='news-item empty-state'>No dispatches yet.</li>";
            return;
        }

        list.innerHTML = events.reverse().map(evt => {
            const label = evt.type.replace(/_/g, " ");
            let text =  "";

            if (evt.type === "match_result") {
                text = `${evt.home_team} ${evt.home_goals}-${evt.away_goals} ${evt.away_team}`;
            } else if (event.type === "hat-trick") {
                text = `${evt.player} scores a hat-trick for ${evt.team}`;
            } else if (evt.type === "competition_winner") {
                text = `${evt.winner} are crowned ${evt.competition} champions`;
            } else if (evt.type === "record_broken") {
                text = `${evt.holder} new record: ${evt.record_type.replace(/_/g, " ")}`;
            } else {
                text = JSONstringify(evt).slice(0, 60);
            }

            return `
                <li class="news-item">
                    <span class="news-type">${label}</span>
                    ${text}
                </li>
            `
        }).join("");

    } catch (e) {
        console.warn("News refresh failed:", e);
    }
}

// Inbox (right column)

async function refreshInbox() {
    try {
        const items = await api("GET", "/api/inbox?unread_only=false");
        const list = document.getElementById("inbox-list");

        if (!items || items.length === 0) {
            list.innerHTML = "<li class='empty-state'>No correspondence.</li>";
            return;
        }

        list.innerHTML = items.slice(-8).reverse().map(item => `
                <li class="inbox-item">
                    <span class="inbox-tag">${item.category} - ${formatDate(item.date)}</span>
                    ${item.title}
                </li>
            `).join("");

    } catch (e) {
        console.warn("Inbox refresh failed:", e);
    }
}

// Utilities

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function show(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("hidden");
}

function hide(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("hidden");
}

function disable(yes) {
    document.getElementById("btn-advance").disabled = yes;
}

function setStatus(msg) {
    setText("footer-status", msg);
}

function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric"
    });
}

// Init

(async function init() {
    // On load, check if the engine has already been started
    // (for example, the server was restarted but game data exists).
    try {
        const state = await api("GET", "api/state")
        if (state.type !== "not_started") {
            render(state);
            await refreshNews();
            await refreshInbox();
        } else {
            setStatus("Ready. Press Advance to begin.");
        }
    } catch (e) {
        setStatus(`Cannot reach API: ${e.message}`);
    }
})();