from datetime import datetime

from pydantic import BaseModel, Field


class TrainingSessionCreate(BaseModel):
    title: str | None = None
    topic: str = ""
    question_type: str = "mixed"
    difficulty: str = "normal"
    question_count: int = Field(default=10, ge=1, le=20)
    kb_ids: list[int] = Field(default_factory=list)


class TrainingSessionOut(BaseModel):
    id: int
    title: str
    topic: str
    question_type: str
    difficulty: str
    question_count: int
    kb_ids: list[int] | None
    status: str
    total_score: float | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrainingQuestionOut(BaseModel):
    id: int
    session_id: int
    seq: int
    question_type: str
    question: str
    reference_answer: str
    rubric: str
    max_score: float
    citations: list | None
    options: list | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class TrainingAnswerIn(BaseModel):
    question_id: int
    answer: str = Field(default="", max_length=20000)


class TrainingGradeIn(BaseModel):
    answers: list[TrainingAnswerIn]


class TrainingAnswerOut(BaseModel):
    id: int
    session_id: int
    question_id: int
    answer: str
    score: float
    feedback: str
    suggestion: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrainingReportOut(BaseModel):
    session: TrainingSessionOut
    questions: list[TrainingQuestionOut]
    answers: list[TrainingAnswerOut]


class BankBuildIn(BaseModel):
    kb_ids: list[int] = Field(default_factory=list)
    topic: str = ""
    question_type: str = "mixed"
    difficulty: str = "normal"
    count: int = Field(default=10, ge=1, le=30)


class BankBuildOut(BaseModel):
    added: int
    total: int


class BankItemOut(BaseModel):
    id: int
    kb_id: int
    topic: str
    question_type: str
    difficulty: str
    question: str
    reference_answer: str
    rubric: str
    max_score: float
    options: list | None = None
    citations: list | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class BankListOut(BaseModel):
    items: list[BankItemOut]
    total: int


class SubjectOut(BaseModel):
    subject: str
    total: int
    easy: int = 0
    normal: int = 0
    hard: int = 0


class ExamStartIn(BaseModel):
    subject: str = ""
    difficulty: str = "normal"
    count: int = Field(default=10, ge=1, le=50)


class ExamStartOut(BaseModel):
    session: TrainingSessionOut
    questions: list[TrainingQuestionOut]
