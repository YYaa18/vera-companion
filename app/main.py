"""统一入口：同一个 exe 既是启动器也是助手。

    VeraLauncher.exe               -> 启动器
    VeraLauncher.exe --assistant   -> 陪玩助手（由启动器拉起）

打包：pyinstaller build.spec
"""
import os
import sys


def _ensure_path():
    """Make sibling modules importable when frozen or run from anywhere."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import config
        bundle = config.BUNDLE
        if bundle not in sys.path:
            sys.path.insert(0, bundle)
    except Exception:
        pass


def run_launcher():
    import launcher
    launcher.main()


def run_assistant():
    import voice_companion
    voice_companion.main()


def main():
    _ensure_path()
    if "--assistant" in sys.argv:
        run_assistant()
    else:
        run_launcher()


if __name__ == "__main__":
    main()
