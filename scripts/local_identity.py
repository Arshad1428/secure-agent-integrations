import argparse
import secrets

from secure_agent.authz.policies import ROLE_PERMISSIONS
from secure_agent.config import PROJECT_ROOT
from secure_agent.identity.tokens import issue_token


def initialize_environment() -> None:
    env_path = PROJECT_ROOT / ".env"
    template_path = PROJECT_ROOT / ".env.example"

    if env_path.exists():
        raise ValueError(
            ".env already exists. Keep it or edit it manually."
        )

    template = template_path.read_text(encoding="utf-8")
    placeholder = "replace-with-generated-secret"

    if placeholder not in template:
        raise ValueError(
            ".env.example must contain "
            "JWT_SECRET=replace-with-generated-secret"
        )

    content = template.replace(
        placeholder,
        secrets.token_urlsafe(48),
    )

    with env_path.open("x", encoding="utf-8") as file:
        file.write(content)

    try:
        env_path.chmod(0o600)
    except OSError:
        pass

    print("Created .env with a generated JWT signing secret.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local identity administration"
    )

    parser.add_argument(
        "command",
        choices=["init", "token"],
    )

    parser.add_argument(
        "--subject",
        default="demo-user",
    )

    parser.add_argument(
        "--role",
        choices=sorted(ROLE_PERMISSIONS),
        default="operator",
    )

    args = parser.parse_args()

    try:
        if args.command == "init":
            initialize_environment()
        else:
            print(issue_token(args.subject, args.role))

    except (ValueError, OSError) as exc:
        parser.exit(
            status=1,
            message=f"Error: {exc}\n",
        )


if __name__ == "__main__":
    main()