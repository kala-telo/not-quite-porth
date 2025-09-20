from bytecode import Instr, Bytecode, BinaryOp, Compare, Label
from bytecode.flags import CompilerFlags
from dataclasses import dataclass
import importlib.util
import argparse
import marshal
import time
import dis
import re

cells_code = """
class Cells:
    def __init__(self, n):
        self.n = n
        self.arr = []

    def __add__(self, a):
        if isinstance(a, list):
            self.arr = a
        elif isinstance(a, int):
            self.n += a
        elif isinstance(a, Cells):
            if self.arr == []:
                self.arr = a.arr
            else:
                self.n += a.n
        else:
            raise NotImplementedError
        return self

    def get(self):
        return self.arr[self.n]

    def set(self, x):
        self.arr[self.n] = x

    def extend(self, n):
        if isinstance(n, Cells):
            times = n.n
        elif isinstance(n, int):
            times = n
        else:
            raise NotImplementedError(n)
        self.arr.extend([0]*times)

    def fill(self, x):
        for i in range(self.n, len(self.arr)):
            self.arr[i] = x

    def comma(self, x):
        self.arr.append(x)

    def __repr__(self):
        return repr(self.arr)
"""
exec(cells_code)


@dataclass
class Function:
    name: str
    arg_count: int
    ret_count: int
    starts_at: int


def find_names(code: str) -> list[str | Function]:
    tokens = re.finditer(r'(\." [^"]+"|[^ \r\n]+)', code)
    r = []
    for token in tokens:
        token = token.group()
        if token == ":":
            func = Function("", 0, 0, 0)
            func.name = next(tokens).group()
            if next(tokens).group() != "(":
                print("You must provide arity for the function "
                      f"{func.name} in format ( a b -- c d ) where a, b, c "
                      "and d represent arguments and return values")
                exit(-1)
            func.arg_count = 0
            func.ret_count = 0
            while next(tokens).group() != "--":
                func.arg_count += 1
            while next(tokens).group() != ")":
                func.ret_count += 1
            r.append(func)
        elif token in ["constant", "variable", "create"]:
            r.append(next(tokens).group())
    return r


def compile_forth(code: str, variables: list[str]) -> list[Instr]:
    bcode = [Instr('RESUME', 0)]
    tokens = re.finditer(r'(\." [^"]+"|[^ \r\n]+)', code)
    labels = []
    func = None
    functions = {v.name: v for v in variables if isinstance(v, Function)}
    for token in tokens:
        token = token.group()
        if token in variables+["i"]:
            bcode.append(Instr("LOAD_NAME", token))
        elif token in functions:
            bcode.append(Instr("LOAD_NAME", token))
            if functions[token].arg_count > 0:
                bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("PUSH_NULL"))
            if functions[token].arg_count == 1:
                bcode.append(Instr("SWAP", 2))
            elif functions[token].arg_count == 2:
                bcode.append(Instr("SWAP", 3))
                bcode.append(Instr("SWAP", 4))
            # for i in reversed(range(functions[token].arg_count)):
            #     bcode.append(Instr("SWAP", i+2))
            bcode.append(Instr("CALL", functions[token].arg_count))
            if (functions[token].ret_count == 0):
                bcode.append(Instr("POP_TOP"))
            else:
                bcode.append(Instr("LOAD_GLOBAL", (True, "reversed")))
                bcode.append(Instr("SWAP", 2))
                bcode.append(Instr("SWAP", 3))
                bcode.append(Instr("CALL", 1))
                bcode.append(Instr("UNPACK_SEQUENCE", functions[token].ret_count))
        elif token == ":":
            name = next(tokens).group()
            for v in variables:
                if isinstance(v, Function) and v.name == name:
                    func = v
            assert func is not None
            while next(tokens).group() != ")":
                pass
            func.starts_at = len(bcode)
            bcode.append(Instr('RESUME', 0))
            if func.arg_count > 0:
                bcode.append(Instr("LOAD_FAST", "args"))
                bcode.append(Instr("UNPACK_SEQUENCE", func.arg_count))
        elif token == ";":
            func_code = bcode[func.starts_at:]
            for _ in func_code:
                bcode.pop()
            if func.ret_count == 0:
                func_code.append(Instr("RETURN_CONST", None))
            else:
                func_code.append(Instr("BUILD_TUPLE", func.ret_count))
                func_code.append(Instr("RETURN_VALUE"))
            func_code = Bytecode(func_code)
            if func.arg_count > 0:
                func_code.argnames = ("args",)
                func_code.name = func.name
                func_code.flags |= CompilerFlags.VARARGS
            bcode.append(Instr("LOAD_CONST", func_code.to_code()))
            bcode.append(Instr("MAKE_FUNCTION"))
            bcode.append(Instr("STORE_NAME", func.name))
            func = Function("", 0, 0, 0)
        elif token == "cells":
            bcode.append(Instr("LOAD_NAME", "Cells"))
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("PUSH_NULL"))
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("CALL", 1))
        elif token == "@":
            bcode.append(Instr("LOAD_ATTR", (True, "get")))
            bcode.append(Instr("CALL", 0))
        elif token == "!":
            bcode.append(Instr("LOAD_ATTR", (True, "set")))
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("SWAP", 3))
            bcode.append(Instr("CALL", 1))
            bcode.append(Instr("POP_TOP"))
        elif token == "+":
            bcode.append(Instr("BINARY_OP", BinaryOp.ADD))
        elif token == "*":
            bcode.append(Instr("BINARY_OP", BinaryOp.MULTIPLY))
        elif token == "mod":
            bcode.append(Instr("BINARY_OP", BinaryOp.REMAINDER))
        elif token == "1-":
            bcode.append(Instr("LOAD_CONST", 1))
            bcode.append(Instr("BINARY_OP", BinaryOp.SUBTRACT))
        elif token == "1+":
            bcode.append(Instr("LOAD_CONST", 1))
            bcode.append(Instr("BINARY_OP", BinaryOp.ADD))
        elif token == "=":
            bcode.append(Instr("COMPARE_OP", Compare.EQ))
        elif token == "dup":
            bcode.append(Instr("COPY", 1))
        elif token == "swap":
            bcode.append(Instr("SWAP", 2))
        elif token == "over":
            bcode.append(Instr("COPY", 2))
        elif token == "rot":
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("SWAP", 3))
        elif token == "if":
            labels.append(Label())  # false
            labels.append(Label())  # exit
            bcode.append(Instr('POP_JUMP_IF_FALSE', labels[-1]))
        elif token == "else":
            els = labels.pop()
            bcode.append(Instr('JUMP_FORWARD', labels[-1]))
            bcode.append(els)
        elif token == "then":
            bcode.append(labels.pop())
        elif token == "loop":
            loop_end = labels.pop()
            bcode.append(Instr("LOAD_FAST", "_iter"))
            bcode.append(Instr('JUMP_BACKWARD', labels.pop()))
            bcode.append(loop_end)
            bcode.append(Instr("END_FOR"))
            bcode.append(Instr("POP_TOP"))
        elif token == "do":
            labels.append(Label())  # loop start
            labels.append(Label())  # loop end
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("LOAD_NAME", "range"))
            bcode.append(Instr("SWAP", 3))
            bcode.append(Instr("PUSH_NULL"))
            bcode.append(Instr("SWAP", 3))
            bcode.append(Instr("CALL", 2))
            bcode.append(Instr("GET_ITER"))
            bcode.append(labels[-2])
            bcode.append(Instr("FOR_ITER", labels[-1]))
            bcode.append(Instr("STORE_NAME", "i"))
            bcode.append(Instr("STORE_FAST", "_iter"))
        elif token == "constant":
            bcode.append(Instr("STORE_NAME", next(tokens).group()))
        elif token == "variable":
            bcode.append(Instr("LOAD_NAME", "Cells"))
            bcode.append(Instr("PUSH_NULL"))
            bcode.append(Instr("LOAD_CONST", 0))
            bcode.append(Instr("CALL", 1))
            bcode.append(Instr("LOAD_CONST", 0))
            bcode.append(Instr("BUILD_LIST", 1))
            bcode.append(Instr("BINARY_OP", BinaryOp.ADD))
            bcode.append(Instr("COPY", 1))
            bcode.append(Instr("STORE_NAME", next(tokens).group()))
            bcode.append(Instr("STORE_NAME", "_last_allot"))
        elif token == "create":
            bcode.append(Instr("LOAD_NAME", "Cells"))
            bcode.append(Instr("PUSH_NULL"))
            bcode.append(Instr("LOAD_CONST", 0))
            bcode.append(Instr("CALL", 1))
            bcode.append(Instr("COPY", 1))
            bcode.append(Instr("STORE_NAME", next(tokens).group()))
            bcode.append(Instr("STORE_NAME", "_last_allot"))
        elif token == "allot":
            bcode.append(Instr("LOAD_NAME", "_last_allot"))
            bcode.append(Instr("LOAD_ATTR", (True, "extend")))
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("SWAP", 3))
            bcode.append(Instr("CALL", 1))
            bcode.append(Instr("POP_TOP"))
        elif token == "fill":
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("LOAD_ATTR", (True, "fill")))
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("SWAP", 3))
            bcode.append(Instr("CALL", 1))
            bcode.append(Instr("POP_TOP"))
        elif token == ",":
            bcode.append(Instr("LOAD_NAME", "_last_allot"))
            bcode.append(Instr("LOAD_ATTR", (True, "comma")))
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("SWAP", 3))
            bcode.append(Instr("CALL", 1))
            bcode.append(Instr("POP_TOP"))
        elif token.isdigit():
            bcode.append(Instr("LOAD_CONST", int(token)))
        elif token.startswith('." ') and token.endswith('"'):
            bcode.append(Instr("LOAD_GLOBAL", (True, "print")))
            s = token.removeprefix('." ').removesuffix('"')
            bcode.append(Instr("LOAD_CONST", s))
            bcode.append(Instr("LOAD_CONST", ''))
            bcode.append(Instr("LOAD_CONST", ('end',)))
            bcode.append(Instr("CALL_KW", 2))
            bcode.append(Instr("POP_TOP"))
        elif token == "cr":
            bcode.append(Instr("LOAD_NAME", "print"))
            bcode.append(Instr("PUSH_NULL"))
            bcode.append(Instr("CALL", 0))
            bcode.append(Instr("POP_TOP"))
        elif token == "bye":
            bcode.append(Instr("LOAD_NAME", "exit"))
            bcode.append(Instr("PUSH_NULL"))
            bcode.append(Instr("CALL", 0))
            bcode.append(Instr("POP_TOP"))
        elif token == ".":
            bcode.append(Instr("LOAD_NAME", "print"))
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("PUSH_NULL"))
            bcode.append(Instr("SWAP", 2))
            bcode.append(Instr("LOAD_CONST", ''))
            bcode.append(Instr("LOAD_CONST", ('end',)))
            bcode.append(Instr("CALL_KW", 2))
            bcode.append(Instr("POP_TOP"))
        else:
            print(token)
            raise NotImplementedError

    bcode.append(Instr('RETURN_CONST', None))
    return bcode


parser = argparse.ArgumentParser(
    description="Forth to Python bytecode compiler")
parser.add_argument("filename")
parser.add_argument("-r", '--run', help="Run the program", action="store_true")
parser.add_argument("-d", '--dis', help="Print disassembly", action="store_true")
parser.add_argument("-c", '--compile', help="Put the code into .pyc file")
args = parser.parse_args()
with open(args.filename, "r") as f:
    code = f.read()
    pcode = compile_forth(code, find_names(code))
if args.dis:
    dis.dis(Bytecode(pcode).to_code())
if args.compile:
    with open(args.compile, "wb") as f:
        f.write(importlib.util.MAGIC_NUMBER)
        f.write(b"\x00\x00\x00\x00")
        f.write(int(time.time()).to_bytes(4, 'little'))
        f.write(b"\x00\x00\x00\x00")
        # -1 for RETURN
        pcode = Bytecode.from_code(
            compile(cells_code, "<cells>", "exec"))[:-1] + pcode
        marshal.dump(Bytecode(pcode).to_code(), f)
if args.run:
    exec(Bytecode(pcode).to_code())
if not (args.dis or args.compile or args.run):
    parser.print_help()
