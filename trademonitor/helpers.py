from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import re
import json

@dataclass
class JSVariable:
    name: str
    value: Any

@dataclass
class JSVariableExtractor:
    html_text: str
    variables: Dict[str, JSVariable] = field(default_factory=dict)

    def extract(self) -> Dict[str, JSVariable]:
        script_blocks: List[str] = self._extract_script_blocks(self.html_text)
        for script in script_blocks:
            self._extract_from_script(script)
        return self.variables

    def _extract_script_blocks(self, html: str) -> List[str]:
        pattern = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
        return [m.strip() for m in pattern.findall(html)]

    def _extract_from_script(self, script: str) -> None:
        decl_pattern = re.compile(r'\b(var|let|const)\s+([a-zA-Z_$][\w$]*)\s*=\s*', re.DOTALL)
        for match in decl_pattern.finditer(script):
            var_name: str = match.group(2)
            start_index: int = match.end()

            value, _ = self._read_until_semicolon(script, start_index)
            if value is not None:
                parsed_value: Any = self._clean_value(value)
                self.variables[var_name] = JSVariable(name=var_name, value=parsed_value)

    def _read_until_semicolon(self, script: str, start_index: int) -> Tuple[Optional[str], int]:
        i: int = start_index
        depth: int = 0
        in_str: Optional[str] = None
        escape: bool = False

        while i < len(script):
            char: str = script[i]

            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif in_str:
                if char == in_str:
                    in_str = None
            elif char in ('"', "'"):
                in_str = char
            elif char in '{[(':
                depth += 1
            elif char in '}])':
                depth -= 1
            elif char == ';' and depth <= 0:
                return script[start_index:i].strip(), i
            i += 1

        return None, len(script)

    def _clean_value(self, raw: str) -> Any:
        raw = raw.strip()
        try:
            if raw.startswith(("'", '"')):
                return json.loads(raw.replace("'", '"'))
            elif raw.startswith('{') or raw.startswith('['):
                return json.loads(raw)
            elif raw.lower() in ('true', 'false'):
                return raw.lower() == 'true'
            elif raw == 'null':
                return None
            elif re.match(r'^-?\d+$', raw):
                return int(raw)
        except Exception:
            pass
        return raw

def _extract_past_owners(html: str) -> List[int]:
    card_divs = re.findall(
        r'<div class="card rounded-0 my-2 shadow border-0">(.*?)</div>', 
        html, 
        re.DOTALL
    )
    
    results = []
    for card_html in card_divs:
        match = re.search(r'href="/player/(\d+)"', card_html)
        if match and int(match.group(1)) not in results:
            results.append(int(match.group(1)))
        
    return results