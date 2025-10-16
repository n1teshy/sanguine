from tree_sitter_language_pack import get_parser

import sanguine.constants as c
from sanguine.utils import prog_lang_schema


def extract_symbols(code: str, lang: str) -> dict:
    result = {c.FLD_FUNCTIONS: [], c.FLD_CLASSES: []}
    nodes = prog_lang_schema.get(lang.lower())

    if not nodes:
        return result

    parser = get_parser(lang)
    code_bytes = code.encode("utf8")
    tree = parser.parse(code_bytes)
    root = tree.root_node

    def extract_name(node):
        for child in node.children:
            if child.type == nodes["identifier"]:
                return code_bytes[child.start_byte : child.end_byte].decode(
                    "utf8"
                )
        return None

    def traverse(node):
        if node.type == nodes["function"]:
            name = extract_name(node)
            if name:
                result[c.FLD_FUNCTIONS].append(name)

        elif node.type == nodes["class"]:
            name = extract_name(node)
            if name:
                result[c.FLD_CLASSES].append(name)

        for child in node.children:
            traverse(child)

    traverse(root)
    return result
