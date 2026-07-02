# HDS Agent Package
# Authors: Denys Uvarov, Mykyta Aleksandrov, Anastasiia Uvarova
# License: HDS Standard


def __getattr__(name):
    # Lazy export: agent.py and its deps use flat imports (from model_router
    # import ...) that need agent/ on sys.path; loading eagerly here would
    # break plain `import agent`. Loaded via file location to avoid the
    # package/module name collision (agent/agent.py).
    if name == "HDSAgent":
        import sys, importlib.util, os
        _dir = os.path.dirname(__file__)
        if _dir not in sys.path:
            sys.path.insert(0, _dir)
        spec = importlib.util.spec_from_file_location(
            "_agent_module", os.path.join(_dir, "agent.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        globals()["HDSAgent"] = mod.HDSAgent
        return mod.HDSAgent
    raise AttributeError(f"module 'agent' has no attribute {name!r}")


__all__ = ["HDSAgent"]
