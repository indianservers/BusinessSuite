import pytest
from pydantic import ValidationError
from app.forms.schema import Question

@pytest.mark.parametrize("width", ["auto", "full", "half", "third", "two-thirds", "quarter", "three-quarters"])
def test_canvas_layout_roundtrip(width):
    field = Question(id="name", type="text", label="Name", width=width, height=160)
    restored = Question.model_validate_json(field.model_dump_json())
    assert restored.width == width
    assert restored.height == 160

@pytest.mark.parametrize("height", [47, 601])
def test_canvas_height_bounds(height):
    with pytest.raises(ValidationError):
        Question(id="name", type="text", label="Name", height=height)

def test_legacy_canvas_layout():
    field = Question(id="name", type="text", label="Name")
    assert field.width == "auto"
    assert field.height is None
