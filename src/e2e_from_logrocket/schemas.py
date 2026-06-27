from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FlowStep(BaseModel):
    order: int
    action: Literal[
        "navigate",
        "click",
        "fill",
        "select",
        "hover",
        "wait",
        "assert_visible",
        "assert_text",
        "assert_url",
    ]
    target: str = Field(
        description="Human-readable target: button text, label, role+name, or CSS hint"
    )
    value: str | None = None
    url: str | None = None
    notes: str | None = None


class SyntheticTestData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str
    first_name: str = Field(serialization_alias="firstName")
    last_name: str = Field(serialization_alias="lastName")
    full_name: str = Field(serialization_alias="fullName")
    phone: str
    company: str
    address_line1: str = Field(serialization_alias="addressLine1")
    city: str
    state: str
    postal_code: str = Field(serialization_alias="postalCode")
    password: str


class ApiMock(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    method: str = "GET"
    url_pattern: str = Field(validation_alias="urlPattern")
    fixture_file: str = Field(validation_alias="fixtureFile")
    status: int = 200
    description: str | None = None
    transform_response: bool = Field(default=False, validation_alias="transformResponse")


class NormalizedFlow(BaseModel):
    name: str
    source_session_ids: list[str]
    start_url: str
    persona: str | None = None
    steps: list[FlowStep]
    assertions: list[str] = Field(default_factory=list)
    flaky_risks: list[str] = Field(default_factory=list)
    pii_redacted: bool = False
    test_data: SyntheticTestData | None = None
    api_mocks: list[ApiMock] = Field(default_factory=list)


class GeneratedTest(BaseModel):
    filename: str
    framework: Literal["playwright"] = "playwright"
    code: str
    flow_name: str
    rationale: str
