from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from faker import Faker

from ..schemas import ApiMock, NormalizedFlow, SyntheticTestData

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"
)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@dataclass
class SanitizedArtifacts:
    text: str
    test_data: SyntheticTestData
    replacements: dict[str, str] = field(default_factory=dict)


class PIISanitizer:
    """Deterministic Faker-based redaction for production session data."""

    def __init__(self, seed: int = 42, locale: str = "en_US") -> None:
        self._seed = seed
        self._faker = Faker(locale)
        self._replacements: dict[str, str] = {}

    @property
    def replacements(self) -> dict[str, str]:
        return dict(self._replacements)

    def _token_seed(self, value: str) -> int:
        digest = hashlib.sha256(f"{self._seed}:{value}".encode()).hexdigest()
        return int(digest[:8], 16)

    def _fake_for(self, kind: str, original: str) -> str:
        if original in self._replacements:
            return self._replacements[original]

        fake = Faker()
        fake.seed_instance(self._token_seed(f"{kind}:{original}"))

        generators = {
            "email": fake.email,
            "phone": fake.phone_number,
            "ssn": fake.ssn,
            "card": fake.credit_card_number,
            "uuid": fake.uuid4,
            "ip": fake.ipv4,
            "name": fake.name,
            "address": fake.address,
            "company": fake.company,
            "text": fake.sentence,
        }
        synthetic = generators.get(kind, fake.word)()
        self._replacements[original] = synthetic
        return synthetic

    def sanitize_text(self, text: str) -> str:
        result = text
        for pattern, kind in (
            (EMAIL_RE, "email"),
            (PHONE_RE, "phone"),
            (SSN_RE, "ssn"),
            (CARD_RE, "card"),
            (UUID_RE, "uuid"),
            (IP_RE, "ip"),
        ):
            result = pattern.sub(lambda m, k=kind: self._fake_for(k, m.group(0)), result)
        return result

    def build_test_data(self, flow_name: str) -> SyntheticTestData:
        fake = Faker()
        fake.seed_instance(self._token_seed(f"flow:{flow_name}"))
        return SyntheticTestData(
            email=fake.email(),
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            full_name=fake.name(),
            phone=fake.phone_number(),
            company=fake.company(),
            address_line1=fake.street_address(),
            city=fake.city(),
            state=fake.state_abbr(),
            postal_code=fake.postcode(),
            password=f"Test!{fake.uuid4()[:8]}",
        )

    def apply_test_data_to_flow(self, flow: NormalizedFlow, test_data: SyntheticTestData) -> NormalizedFlow:
        """Replace fill values that look like PII with stable synthetic placeholders."""
        data = test_data.model_dump()
        updated_steps = []

        for step in flow.steps:
            if step.action != "fill" or not step.value:
                updated_steps.append(step)
                continue

            value = step.value
            target = step.target.lower()

            if EMAIL_RE.search(value):
                value = data["email"]
            elif PHONE_RE.search(value):
                value = data["phone"]
            elif "password" in target:
                value = data["password"]
            elif "first" in target and "name" in target:
                value = data["first_name"]
            elif "last" in target and "name" in target:
                value = data["last_name"]
            elif "name" in target:
                value = data["full_name"]
            elif "company" in target:
                value = data["company"]
            elif "address" in target:
                value = data["address_line1"]
            elif "city" in target:
                value = data["city"]
            elif "state" in target:
                value = data["state"]
            elif "zip" in target or "postal" in target:
                value = data["postal_code"]
            elif SSN_RE.search(value) or CARD_RE.search(value):
                value = self._fake_for("ssn" if SSN_RE.search(step.value) else "card", step.value)

            updated_steps.append(step.model_copy(update={"value": value}))

        return flow.model_copy(update={"steps": updated_steps, "pii_redacted": True})

    def sanitize_flow_bundle(
        self,
        flow: NormalizedFlow,
        session_text: str,
    ) -> tuple[NormalizedFlow, SanitizedArtifacts, list[ApiMock]]:
        sanitized_text = self.sanitize_text(session_text)
        test_data = self.build_test_data(flow.name)
        redacted_flow = self.apply_test_data_to_flow(flow, test_data)

        api_mocks = self._infer_api_mocks(sanitized_text, redacted_flow)
        artifacts = SanitizedArtifacts(
            text=sanitized_text,
            test_data=test_data,
            replacements=self.replacements,
        )
        return redacted_flow.model_copy(update={"test_data": test_data, "api_mocks": api_mocks}), artifacts, api_mocks

    def _infer_api_mocks(self, session_text: str, flow: NormalizedFlow) -> list[ApiMock]:
        """Heuristic extraction of API calls mentioned in session analysis."""
        mocks: list[ApiMock] = []
        seen: set[str] = set()

        api_patterns = [
            re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[\w./?=&-]+)", re.I),
            re.compile(r"\b(/api/[\w./?=&-]+)"),
            re.compile(r"https?://[^\s\"']+/api/[\w./?=&-]+"),
        ]

        for pattern in api_patterns:
            for match in pattern.finditer(session_text):
                if len(match.groups()) == 2:
                    method, path = match.group(1).upper(), match.group(2)
                else:
                    method, path = "GET", match.group(1)

                if "logrocket" in path.lower():
                    continue

                key = f"{method}:{path}"
                if key in seen:
                    continue
                seen.add(key)

                slug = re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower())[:48] or "root"
                mocks.append(
                    ApiMock(
                        method=method,
                        url_pattern=f"**{path.split('?')[0]}*",
                        fixture_file=f"{slug}.json",
                        description=f"Inferred from session replay ({method} {path})",
                    )
                )

        if not mocks and flow.name:
            mocks.append(
                ApiMock(
                    method="GET",
                    url_pattern="**/api/**",
                    fixture_file="default-api.json",
                    description="Fallback mock for API traffic during regression",
                    transform_response=True,
                )
            )

        return mocks[:8]

    def default_fixture_body(self, mock: ApiMock, test_data: SyntheticTestData) -> str:
        payload = {
            "id": self._fake_for("uuid", mock.fixture_file),
            "email": test_data.email,
            "firstName": test_data.first_name,
            "lastName": test_data.last_name,
            "message": "synthetic fixture — no production PII",
        }
        return json.dumps(payload, indent=2)

    def sanitize_json(self, value: Any) -> Any:
        """Recursively redact PII inside JSON API payloads."""
        if isinstance(value, str):
            return self.sanitize_text(value)
        if isinstance(value, list):
            return [self.sanitize_json(item) for item in value]
        if isinstance(value, dict):
            return {key: self.sanitize_json(item) for key, item in value.items()}
        return value

    def sanitize_response_body(self, body: str, content_type: str = "") -> str:
        if "json" in content_type.lower():
            try:
                parsed = json.loads(body)
                return json.dumps(self.sanitize_json(parsed), indent=2)
            except json.JSONDecodeError:
                pass
        return self.sanitize_text(body)
