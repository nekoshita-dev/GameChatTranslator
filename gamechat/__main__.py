import sys

if sys.version_info < (3, 11):
    print("GameChat Translator には Python 3.11 以上が必要です"
          f"（今は {sys.version_info.major}.{sys.version_info.minor}）。"
          "python.org から 3.11 か 3.12 を入れ直して、setup.bat を実行してください。")
    sys.exit(1)

from .app import main  # noqa: E402

main()
