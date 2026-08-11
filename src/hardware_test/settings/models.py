"""Models for secret-bearing runtime configuration."""

from pydantic import BaseModel, Field, SecretStr


class SshCredentialSettings(BaseModel):
    """Credentials used by an SSH transport."""

    username: str
    password: SecretStr


class CredentialSettings(BaseModel):
    """Named SSH credential profiles referenced by inventory."""

    default_ssh: SshCredentialSettings | None = None
    analyzer_default: SshCredentialSettings | None = None
    generator_default: SshCredentialSettings | None = None
    ssh: dict[str, SshCredentialSettings] = Field(default_factory=dict)

    def get_ssh(self, name: str) -> SshCredentialSettings | None:
        """Resolve a kebab-case inventory credential reference."""
        built_in = {
            "default-ssh": self.default_ssh,
            "analyzer-default": self.analyzer_default,
            "generator-default": self.generator_default,
        }
        return built_in.get(name) or self.ssh.get(name)
