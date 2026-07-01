# HDS Agent Package
# Authors: Denys Uvarov, Mykyta Aleksandrov, Anastasiia Uvarova
# License: HDS Standard

def __getattr__(name):
    if name in ("HDSAgent", "HDS6Agent"):
        import sys, importlib.util, os
        _dir = os.path.dirname(__file__)
        if _dir not in sys.path:
            sys.path.insert(0, _dir)
        spec = importlib.util.spec_from_file_location("_agent_module",
                                                       os.path.join(_dir, "agent.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _cls = mod.HDSAgent
        globals()["HDSAgent"] = _cls
        globals()["HDS6Agent"] = _cls
        return _cls
    raise AttributeError(f"module 'agent' has no attribute {name!r}")

__all__ = ["HDSAgent", "HDS6Agent"]
