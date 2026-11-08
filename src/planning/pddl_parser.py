"""
pddl_parser.py - Subset PDDL Parser (Domain & Problem)

Mendukung subset PDDL yang terbaca manusia:
  - Domain: (:predicates ...), (:action <name> :parameters (...) :precondition (...) :effect (...) [:cost <expr>])
  - Problem: (:objects ...), (:init ...), (:goal ...), [(:metric minimize ...)]
  - Efek: konjungsi (and ...), delete effect (not (...)), add effect ((...))
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set


class PDDLParseError(Exception):
    """Exception untuk kesalahan sintaks pada domain atau problem PDDL."""
    pass


@dataclass
class PredicateDef:
    name: str
    params: List[str] = field(default_factory=list)


@dataclass
class ActionDef:
    name: str
    parameters: List[str] = field(default_factory=list)
    precondition: List[Any] = field(default_factory=list)     # list of literals (pos/neg)
    effect_add: List[Any] = field(default_factory=list)       # list of add literals
    effect_del: List[Any] = field(default_factory=list)       # list of del literals
    cost_expr: Optional[Any] = None                           # ekspresi biaya aksi (angka atau nama fungsi)


@dataclass
class DomainAST:
    name: str
    predicates: Dict[str, PredicateDef] = field(default_factory=dict)
    actions: Dict[str, ActionDef] = field(default_factory=dict)
    constants: Dict[str, str] = field(default_factory=dict)   # name -> type


@dataclass
class ProblemAST:
    name: str
    domain_name: str
    objects: Dict[str, str] = field(default_factory=dict)     # obj_name -> type
    init_facts: Set[Tuple[str, ...]] = field(default_factory=set)
    goal_facts: Set[Tuple[str, ...]] = field(default_factory=set)
    metric: Optional[str] = None


def tokenize(text: str) -> List[Tuple[str, int, int]]:
    """
    Memecah teks PDDL menjadi token (token_str, line_no, col_no).
    Mengabaikan komentar bertanda ';' sampai akhir baris.
    """
    tokens = []
    lines = text.split("\n")
    for line_idx, line in enumerate(lines, start=1):
        # Hapus komentar
        comment_idx = line.find(";")
        if comment_idx >= 0:
            line = line[:comment_idx]

        col_idx = 0
        n = len(line)
        while col_idx < n:
            char = line[col_idx]
            if char.isspace():
                col_idx += 1
                continue
            if char in "()":
                tokens.append((char, line_idx, col_idx + 1))
                col_idx += 1
                continue

            # Token kata/simbol
            start_col = col_idx + 1
            start_idx = col_idx
            while col_idx < n and not line[col_idx].isspace() and line[col_idx] not in "()":
                col_idx += 1
            tok = line[start_idx:col_idx]
            tokens.append((tok, line_idx, start_col))
    return tokens


def parse_sexpr(tokens: List[Tuple[str, int, int]]) -> Tuple[Any, int]:
    """Mengonversi daftar token menjadi representasi pohon S-expression (nested list)."""
    if not tokens:
        raise PDDLParseError("Teks PDDL kosong atau tidak lengkap!")

    tok, line, col = tokens[0]
    if tok != "(":
        return tok, 1

    expr = []
    idx = 1
    while idx < len(tokens):
        current_tok, cur_line, cur_col = tokens[idx]
        if current_tok == ")":
            return expr, idx + 1
        elif current_tok == "(":
            sub_expr, consumed = parse_sexpr(tokens[idx:])
            expr.append(sub_expr)
            idx += consumed
        else:
            expr.append(current_tok)
            idx += 1

    raise PDDLParseError(f"Tanda kurung '(' di baris {line}, kolom {col} tidak ditutup!")


def parse_all_sexprs(tokens: List[Tuple[str, int, int]]) -> List[Any]:
    """Mengurai seluruh S-expression dalam file."""
    exprs = []
    idx = 0
    while idx < len(tokens):
        sub_expr, consumed = parse_sexpr(tokens[idx:])
        exprs.append(sub_expr)
        idx += consumed
    return exprs


# ==============================================================================
# PARSER DOMAIN
# ==============================================================================
def parse_domain(text: str) -> DomainAST:
    """Membaca teks PDDL domain dan mengembalikan DomainAST."""
    tokens = tokenize(text)
    exprs = parse_all_sexprs(tokens)
    if not exprs:
        raise PDDLParseError("File domain PDDL kosong!")

    # Format utama: (define (domain <name>) ...)
    root = exprs[0]
    if not isinstance(root, list) or len(root) < 2 or root[0].lower() != "define":
        raise PDDLParseError("Domain harus diawali dengan '(define (domain <nama>) ...)'")

    domain_decl = root[1]
    if not isinstance(domain_decl, list) or len(domain_decl) < 2 or domain_decl[0].lower() != "domain":
        raise PDDLParseError("Deklarasi nama domain tidak valid!")
    domain_name = domain_decl[1]

    domain = DomainAST(name=domain_name)

    for item in root[2:]:
        if not isinstance(item, list) or not item:
            continue
        tag = item[0].lower()
        if tag == ":predicates":
            _parse_predicates(domain, item[1:])
        elif tag == ":constants":
            _parse_typed_list(domain.constants, item[1:])
        elif tag == ":action":
            _parse_action(domain, item[1:])
        elif tag in (":requirements", ":types"):
            # Kita catat atau abaikan jika subset tidak membutuhkan hierarki tipe kompleks
            pass

    return domain


def _parse_predicates(domain: DomainAST, pred_list: List[Any]):
    for item in pred_list:
        if isinstance(item, list) and item:
            p_name = item[0]
            p_params = [p for p in item[1:] if p != "-"]
            domain.predicates[p_name] = PredicateDef(name=p_name, params=p_params)


def _parse_typed_list(target_dict: Dict[str, str], items: List[str]):
    # Menangani pola 'obj1 obj2 - type obj3 - type2'
    pending = []
    idx = 0
    while idx < len(items):
        item = items[idx]
        if item == "-":
            type_name = items[idx + 1] if idx + 1 < len(items) else "object"
            for p in pending:
                target_dict[p] = type_name
            pending = []
            idx += 2
        else:
            pending.append(item)
            idx += 1
    for p in pending:
        target_dict[p] = "object"


def _parse_action(domain: DomainAST, action_body: List[Any]):
    if not action_body:
        raise PDDLParseError("Definisi aksi kosong!")
    act_name = action_body[0]

    params = []
    precond = []
    effect_add = []
    effect_del = []
    cost_expr = None

    idx = 1
    while idx < len(action_body):
        key = action_body[idx]
        if key == ":parameters":
            raw_params = action_body[idx + 1]
            if isinstance(raw_params, list):
                # Ekstrak nama parameter (abaikan tanda '-' dan tipe untuk STRIPS murni)
                p_list = []
                p_idx = 0
                while p_idx < len(raw_params):
                    p_tok = raw_params[p_idx]
                    if p_tok == "-":
                        p_idx += 2
                    else:
                        p_list.append(p_tok)
                        p_idx += 1
                params = p_list
            idx += 2
        elif key == ":precondition":
            raw_pre = action_body[idx + 1]
            precond = _normalize_conjunction(raw_pre)
            idx += 2
        elif key == ":effect":
            raw_eff = action_body[idx + 1]
            adds, dels = _extract_effects(raw_eff)
            effect_add = adds
            effect_del = dels
            idx += 2
        elif key == ":cost":
            cost_expr = action_body[idx + 1]
            idx += 2
        else:
            idx += 1

    domain.actions[act_name] = ActionDef(
        name=act_name,
        parameters=params,
        precondition=precond,
        effect_add=effect_add,
        effect_del=effect_del,
        cost_expr=cost_expr
    )


def _normalize_conjunction(expr: Any) -> List[Tuple[Any, ...]]:
    """Mengubah ekspresi prasyarat menjadi list tuple literal konjungtif."""
    if not isinstance(expr, list) or not expr:
        return []
    if expr[0].lower() == "and":
        out = []
        for child in expr[1:]:
            if isinstance(child, list) and child:
                out.append(tuple(child))
        return out
    else:
        return [tuple(expr)]


def _extract_effects(expr: Any) -> Tuple[List[Tuple[Any, ...]], List[Tuple[Any, ...]]]:
    """Memisahkan efek add dan del dari klausa efek."""
    adds = []
    dels = []
    if not isinstance(expr, list) or not expr:
        return adds, dels

    clauses = expr[1:] if expr[0].lower() == "and" else [expr]
    for c in clauses:
        if isinstance(c, list) and c:
            if c[0].lower() == "not":
                # Delete effect: (not (pred ...))
                inner = c[1]
                if isinstance(inner, list):
                    dels.append(tuple(inner))
            else:
                adds.append(tuple(c))
    return adds, dels


# ==============================================================================
# PARSER PROBLEM
# ==============================================================================
def parse_problem(text: str) -> ProblemAST:
    """Membaca teks PDDL problem dan mengembalikan ProblemAST."""
    tokens = tokenize(text)
    exprs = parse_all_sexprs(tokens)
    if not exprs:
        raise PDDLParseError("File problem PDDL kosong!")

    root = exprs[0]
    if not isinstance(root, list) or len(root) < 2 or root[0].lower() != "define":
        raise PDDLParseError("Problem harus diawali dengan '(define (problem <nama>) ...)'")

    prob_decl = root[1]
    if not isinstance(prob_decl, list) or len(prob_decl) < 2 or prob_decl[0].lower() != "problem":
        raise PDDLParseError("Deklarasi nama problem tidak valid!")
    prob_name = prob_decl[1]

    domain_name = ""
    objects = {}
    init_facts = set()
    goal_facts = set()
    metric = None

    for item in root[2:]:
        if not isinstance(item, list) or not item:
            continue
        tag = item[0].lower()
        if tag == ":domain":
            domain_name = item[1]
        elif tag == ":objects":
            _parse_typed_list(objects, item[1:])
        elif tag == ":init":
            for fact in item[1:]:
                if isinstance(fact, list) and fact:
                    init_facts.add(tuple(fact))
        elif tag == ":goal":
            raw_goal = item[1]
            norm_goals = _normalize_conjunction(raw_goal)
            for g in norm_goals:
                goal_facts.add(g)
        elif tag == ":metric":
            # e.g. (:metric minimize (total-cost))
            if len(item) > 2:
                metric = f"{item[1]} {' '.join(str(x) for x in item[2:]) if isinstance(item[2], list) else item[2]}"
            elif len(item) > 1:
                metric = str(item[1])

    return ProblemAST(
        name=prob_name,
        domain_name=domain_name,
        objects=objects,
        init_facts=init_facts,
        goal_facts=goal_facts,
        metric=metric
    )

