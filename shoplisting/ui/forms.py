# # widgets.py
# from wtforms.widgets import html_params

# class DualColorTextWidget(object):
#     def __call__(self, field, **kwargs):
#         print('test')
#         value = field.data or "#000000"
#         color_id = f"{field.id}-color"
#         text_id = f"{field.id}-text"

#         html = f"""
#         <input type="color" id="{color_id}" value="{value}">
#         <input type="text" id="{text_id}" value="{value}">
#         <input type="hidden" {html_params(name=field.name, id=field.id, value=value)}>

#         <script>
#         (function() {{
#             const color = document.getElementById("{color_id}");
#             const text = document.getElementById("{text_id}");
#             const hidden = document.getElementById("{field.id}");

#             function sync(val) {{
#                 hidden.value = val;
#                 text.value = val;
#                 color.value = val;
#             }}

#             color.addEventListener("input", e => sync(e.target.value));
#             text.addEventListener("input", e => sync(e.target.value));
#         }})();
#         </script>
#         """
#         return html

# # fields.py
# from wtforms import StringField

# class DualColorTextField(StringField):
#     widget = DualColorTextWidget()

#     # def _value(self):
#     #     return self.data or "#000000"

#     # def process_formdata(self, valuelist):
#     #     if valuelist:
#     #         self.data = valuelist[0]


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