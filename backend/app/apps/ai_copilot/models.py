from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base_class import Base


class AIProviderSetting(Base):
    __tablename__ = "ai_provider_settings"

    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String(80), nullable=False, index=True)
    model_name = Column(String(120), nullable=False)
    enabled = Column(Boolean, default=False, index=True)
    masked_api_key_reference = Column(String(180))
    data_sharing_allowed = Column(Boolean, default=False, index=True)
    max_tokens = Column(Integer, default=1200)
    temperature = Column(Float, default=0.2)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AIPromptTemplate(Base):
    __tablename__ = "ai_prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    use_case = Column(String(80), nullable=False, index=True)
    module_name = Column(String(80), nullable=False, index=True)
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=False)
    output_schema_json = Column(JSON)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIPromptRun(Base):
    __tablename__ = "ai_prompt_runs"

    id = Column(Integer, primary_key=True, index=True)
    use_case = Column(String(80), nullable=False, index=True)
    provider = Column(String(80), index=True)
    model = Column(String(120))
    record_type = Column(String(80), index=True)
    record_id = Column(Integer, index=True)
    input_token_estimate = Column(Integer, default=0)
    output_token_estimate = Column(Integer, default=0)
    status = Column(String(40), default="created", index=True)
    error_message = Column(Text)
    prompt_template_id = Column(Integer, ForeignKey("ai_prompt_templates.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIRecordSummary(Base):
    __tablename__ = "ai_record_summaries"

    id = Column(Integer, primary_key=True, index=True)
    prompt_run_id = Column(Integer, ForeignKey("ai_prompt_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    module_name = Column(String(80), nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    source_summary_json = Column(JSON)
    confidence = Column(Float, default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIScore(Base):
    __tablename__ = "ai_scores"

    id = Column(Integer, primary_key=True, index=True)
    prompt_run_id = Column(Integer, ForeignKey("ai_prompt_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    use_case = Column(String(80), nullable=False, index=True)
    module_name = Column(String(80), nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    score = Column(Float, default=0)
    probability = Column(Float, default=0)
    label = Column(String(80))
    reasons_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    prompt_run_id = Column(Integer, ForeignKey("ai_prompt_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    use_case = Column(String(80), nullable=False, index=True)
    module_name = Column(String(80), nullable=False, index=True)
    record_type = Column(String(80), index=True)
    record_id = Column(Integer, index=True)
    recommendation_text = Column(Text, nullable=False)
    confidence = Column(Float, default=0)
    reasons_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIAgentAction(Base):
    __tablename__ = "ai_agent_actions"

    id = Column(Integer, primary_key=True, index=True)
    prompt_run_id = Column(Integer, ForeignKey("ai_prompt_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    action_type = Column(String(80), nullable=False, index=True)
    module_name = Column(String(80), nullable=False, index=True)
    record_type = Column(String(80), index=True)
    record_id = Column(Integer, index=True)
    preview_json = Column(JSON)
    result_json = Column(JSON)
    status = Column(String(40), default="previewed", index=True)
    requires_confirmation = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    confirmed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    confirmed_at = Column(DateTime(timezone=True))


class AIActionLog(Base):
    __tablename__ = "ai_action_logs"

    id = Column(Integer, primary_key=True, index=True)
    prompt_run_id = Column(Integer, ForeignKey("ai_prompt_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_action_id = Column(Integer, ForeignKey("ai_agent_actions.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    module_name = Column(String(80), index=True)
    record_type = Column(String(80), index=True)
    record_id = Column(Integer, index=True)
    status = Column(String(40), nullable=False, index=True)
    detail_json = Column(JSON)
    error_message = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIUserFeedback(Base):
    __tablename__ = "ai_user_feedback"

    id = Column(Integer, primary_key=True, index=True)
    prompt_run_id = Column(Integer, ForeignKey("ai_prompt_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendation_id = Column(Integer, ForeignKey("ai_recommendations.id", ondelete="SET NULL"), nullable=True, index=True)
    rating = Column(String(40), nullable=False, index=True)
    comments = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

