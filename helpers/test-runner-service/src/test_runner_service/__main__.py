import uvicorn


def main() -> None:
    uvicorn.run(
        "test_runner_service.main:create_app",
        factory=True,
        host="0.0.0.0",  # noqa: S104 - exposure is controlled by Compose port binding.
        port=8080,
        workers=1,
    )


if __name__ == "__main__":
    main()
