from wtforms import StringField
from wtforms.widgets import TextInput

class ColorTextWidget(TextInput):
    def __call__(self, field, **kwargs):
        color_value = field.data or "#123456"
        color_id = f"{field.id}-color"
        text_id = f"{field.id}-text"

        return f"""
            <div style="display: flex; gap: 10px; align-items: center;">
                <input id="{color_id}" type="color"
                       name="{field.name}"
                       value="{color_value}"
                       style="width: 60px; height: 40px; border: none; cursor: pointer;" />

                <input id="{text_id}" type="text"
                       name="{field.name}"
                       value="{color_value}"
                       style="width: 120px;" />
            </div>
            <script>
            (function() {{
                const color = document.getElementById("{color_id}");
                const text = document.getElementById("{text_id}");

                function sync(val) {{
                    text.value = val;
                    color.value = val;
                }}

                color.addEventListener("input", e => sync(e.target.value));
                text.addEventListener("input", e => sync(e.target.value));
            }})();
            </script>
        """

class ColorTextField(StringField):
    widget = ColorTextWidget()