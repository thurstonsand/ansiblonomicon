#!/usr/bin/python3
import os


def main() -> None:
    os.execv(
        "/usr/local/bin/storage-alert",
        [
            "/usr/local/bin/storage-alert",
            f"SMART {os.environ['SMARTD_FAILTYPE']}: {os.environ['SMARTD_DEVICE']}",
            os.environ["SMARTD_FULLMESSAGE"],
        ],
    )


if __name__ == "__main__":
    main()
