import re

class MathProtector:
    def __init__(self):
        self.placeholders = {}
        # Patrones para detectar LaTeX:
        # 1. $$ ... $$  (Ecuaciones en bloque)
        # 2. \[ ... \]  (Ecuaciones en bloque)
        # 3. \( ... \)  (Matemática inline)
        # 4. $ ... $    (Matemática inline)
        self.math_pattern = re.compile(
            r'(\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)|(?<!\$)\$.*?\$)', 
            re.DOTALL
        )

    def protect(self, text: str) -> str:
        """Sustituye fórmulas matemáticas por marcadores [[MATH_X]]"""
        self.placeholders.clear()
        
        def replace_match(match):
            idx = len(self.placeholders)
            tag = f"[[MATH_{idx}]]"
            self.placeholders[tag] = match.group(0)
            return tag

        # Reemplazar todas las coincidencias matemáticas por marcadores
        protected_text = self.math_pattern.sub(replace_match, text)
        return protected_text

    def restore(self, text: str) -> str:
        """Restaura los marcadores [[MATH_X]] con sus fórmulas originales"""
        restored_text = text
        for tag, original_math in self.placeholders.items():
            restored_text = restored_text.replace(tag, original_math)
        return restored_text
