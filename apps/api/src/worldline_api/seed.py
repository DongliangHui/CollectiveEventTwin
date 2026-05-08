from __future__ import annotations

from .database import SessionLocal
from .services import seed_p0


def main() -> None:
    with SessionLocal() as session:
        result = seed_p0(session)
    print(result)


if __name__ == "__main__":
    main()

