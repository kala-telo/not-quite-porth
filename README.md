# Forth compiler that compiles to python bytecode
The compiler implements subset of [Forth](https://en.wikipedia.org/wiki/Forth_(programming_language)), while it's not a full
language, it is a turing complete subset, as demonstrated by rule110.fth example.
## Getting started
```sh
$ pip install bytecode # a dependency
$ python main.py -r examples/rule110.fth
$ python main.py -h
```
## Motivation
It is an educational project, to learn more about Python bytecode. You shouldn't, and probably wouldn't be able to use it for anything serious,
better approach would be to compile to Python source code. The bytecode format is unstable, so it is very likely that it will get outdated quickly,
but general idea should stay the same.

## Notes
- Python bytecode is weird and less similar to Forth than I expected
- Python calls functions in a weird way, by storing function name beyond all arguments. While it might make sense for generating from AST, it adds bunch of shuffling for Forth
- There are not that much stack shuffling opcodes
- There is no return stack

## References
- https://docs.python.org/3/library/dis.html
- https://forth-standard.org/standard/words
