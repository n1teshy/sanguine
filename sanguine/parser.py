from tree_sitter_language_pack import get_parser

import sanguine.constants as c
from sanguine.utils import prog_lang_schema


def extract_symbols(code: str, lang: str) -> dict:
    result = {c.FLD_FUNCTIONS: [], c.FLD_CLASSES: []}

    config = prog_lang_schema.get(lang.lower())
    if not config:
        return result

    parser = get_parser(lang)
    b = code.encode("utf8")
    tree = parser.parse(b)
    root = tree.root_node

    def text(n):
        return b[n.start_byte : n.end_byte].decode("utf8")

    def find_all(node, t, out):
        if node.type == t:
            out.append(node)
        for child in node.children:
            find_all(child, t, out)
        return out

    def follow(node, path):
        cur = node
        for t in path:
            nxt = None
            for child in cur.children:
                if child.type == t:
                    nxt = child
                    break
            if nxt is None:
                return None
            cur = nxt
        return cur

    class_names = []
    function_names = []

    for path in config["class_paths"]:
        head, *rest = path
        for start in find_all(root, head, []):
            leaf = follow(start, rest)
            if leaf:
                n = text(leaf).strip()
                if n:
                    class_names.append(n)

    for path in config["function_paths"]:
        head, *rest = path
        for start in find_all(root, head, []):
            leaf = follow(start, rest)
            if leaf:
                n = text(leaf).strip()
                if n:
                    function_names.append(n)

    class_names = list(set(class_names))
    function_names = [n for n in set(function_names) if n not in class_names]

    result[c.FLD_CLASSES] = class_names
    result[c.FLD_FUNCTIONS] = function_names

    return result
