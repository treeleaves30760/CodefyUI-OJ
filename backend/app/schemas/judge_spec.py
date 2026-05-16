from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class InputPatch(BaseModel):
    node_id: str = Field(min_length=1)
    param_overrides: dict[str, Any] = Field(default_factory=dict)


class OutputRead(BaseModel):
    node_id: str = Field(min_length=1)
    port: str = Field(default="output")
    save_as: str = Field(min_length=1)


class Scoring(BaseModel):
    method: Literal["accuracy", "mse", "mae", "exact_match"]
    target_output: str = Field(min_length=1, description="references OutputRead.save_as")
    ground_truth: str | None = Field(default=None, description="path under hidden_test_data")
    threshold: float = Field(default=0.0)
    full_score: float = Field(default=100.0, gt=0)


class JudgeSpec(BaseModel):
    required_node_ids: list[str] = Field(min_length=1)
    input_patches: list[InputPatch] = Field(default_factory=list)
    output_reads: list[OutputRead] = Field(min_length=1)
    scoring: Scoring
    time_limit_seconds: int = Field(default=60, ge=1, le=600)
    memory_limit_mb: int = Field(default=2048, ge=64, le=16384)

    @model_validator(mode="after")
    def scoring_target_must_be_declared(self) -> "JudgeSpec":
        saves = {r.save_as for r in self.output_reads}
        if self.scoring.target_output not in saves:
            raise ValueError(
                f"scoring.target_output '{self.scoring.target_output}' "
                f"not declared in output_reads (have: {sorted(saves)})"
            )
        return self
