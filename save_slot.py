import json, os, shutil

SCHEMA_VERSION = 1

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
        with open(self.path("manifest.json"), encoding="utf-8") as f:
            json.dump({"schema_version": SCHEMA_VERSION, **fields,}, f, indent=2)
            
    def read_manifest(self):
        with open(self.path("manifest.json"), encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema_version") != SCHEMA_VERSION:
            raise RuntimeError("Save was made with a different version of the game.")
        return data