import json, os, shutil

SCHEMA_VERSION = 2
ENGINE_VERSION = 10

class SaveSlot:
    """A folder holding one saved world"""
    def __init__(self, name="default", root="saves"):
        self.dir = os.path.join(str(root), name)
        
    def path(self, filename):
        return os.path.join(self.dir, filename)
    
    def exists(self):
        return os.path.exists(self.path("manifest.json"))
    
    def reset(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(self.dir)
        
    def write_manifest(self, **fields):
        os.makedirs(self.dir, exist_ok=True)
        path = self.path("manifest.json")
        
        try:
            with open(path, encoding="utf-8") as f:
                manifest = json.load(f)
        except FileNotFoundError:
            manifest = {}
            
        manifest.update(fields)
        manifest["schema_version"] = SCHEMA_VERSION
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            
    def read_manifest(self):
        with open(self.path("manifest.json"), encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema_version") != SCHEMA_VERSION:
            raise RuntimeError("Save was made with a different version of the game.")
        return data
    
    def append_action(self, action: dict):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.path("actions.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(action) + "\n")

    def read_actions(self) -> list:
        path = self.path("actions.jsonl")
        if not os.path.exists(path):
            return []
        actions = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    actions.append(json.loads(line))
                except json.JSONDecodeError:   # half-written last line after a crash
                    break
        return actions

    def clear_actions(self):
        if os.path.exists(self.path("actions.jsonl")):
            os.remove(self.path("actions.jsonl"))