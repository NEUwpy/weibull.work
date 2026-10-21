"""图源数学标记：保留显式LaTeX，给文字中的单个数学符号补标准标记。"""
import re
import unicodedata

MATH=re.compile(r'(\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$)')
GREEK=dict(zip('αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ',
               ['alpha','beta','gamma','delta','epsilon','zeta','eta','theta','iota','kappa','lambda','mu','nu','xi','omicron','pi','rho','sigma','tau','upsilon','phi','chi','psi','omega','Gamma','Delta','Theta','Lambda','Xi','Pi','Sigma','Phi','Psi','Omega']))
SUB='₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ᵢⱼₖₙₘₚᵣₛₜᵤᵥₓₐₑₒ'
SUP='⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾'
PATTERN=re.compile(r'(['+''.join(GREEK)+r']|[A-Za-z](?=[̂̃̄'+SUB+SUP+r']))([̂̃̄]?)(['+SUB+r']*)(['+SUP+r']*)')


def normalize_markup(value):
    def replace(match):
        base,accent,sub,sup=match.groups()
        core='\\'+GREEK[base] if base in GREEK else base
        if accent:core={'̂':r'\hat','̃':r'\widetilde','̄':r'\bar'}[accent]+'{'+core+'}'
        if sub:core+='_{'+unicodedata.normalize('NFKC',sub)+'}'
        if sup:core+='^{'+unicodedata.normalize('NFKC',sup)+'}'
        return r'\('+core+r'\)'
    pieces=MATH.split(str(value))
    return ''.join(piece if i%2 else PATTERN.sub(replace,piece) for i,piece in enumerate(pieces))


def unmarked_expressions(value):
    plain=MATH.sub('',str(value))
    return bool(re.search(r'[=^∑∏∫√≤≥≈∝∇]',plain))
