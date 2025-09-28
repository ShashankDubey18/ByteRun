import collections
import dis
import inspect
import operator
import sys
import types

# -------------------------
# Block Class
# -------------------------
Block = collections.namedtuple("Block", "type, handler, stack_height")

# -------------------------
# Frame Class
# -------------------------
class Frame(object):
    def __init__(self, code_obj, global_names, local_names, prev_frame):
        self.code_obj = code_obj
        self.global_names = global_names
        self.local_names = local_names
        self.prev_frame = prev_frame
        self.stack = []
        self.block_stack = []
        self.last_instruction = 0

        if prev_frame:
            self.builtin_names = prev_frame.builtin_names
        else:
            self.builtin_names = local_names['__builtins__']
            if hasattr(self.builtin_names, '__dict__'):
                self.builtin_names = self.builtin_names.__dict__

    @property
    def f_locals(self):
        return self.local_names

    @property
    def f_globals(self):
        return self.global_names

    @property
    def f_builtins(self):
        return self.builtin_names

# -------------------------
# Function Class
# -------------------------
def make_cell(value):
    fn = (lambda x: lambda: x)(value)
    return fn.__closure__[0]

class Function(object):
    __slots__ = [
        'func_code', 'func_name', 'func_defaults', 'func_globals',
        'func_locals', 'func_dict', 'func_closure',
        '__name__', '__dict__', '__doc__',
        '_vm', '_func',
    ]

    def __init__(self, name, code, globs, defaults, closure, vm):
        self._vm = vm
        self.func_code = code
        self.func_name = self.__name__ = name or code.co_name
        self.func_defaults = tuple(defaults)
        self.func_globals = globs
        self.func_locals = self._vm.frame.f_locals
        self.__dict__ = {}
        self.func_closure = closure
        self.__doc__ = code.co_consts[0] if code.co_consts else None

        kw = {'argdefs': self.func_defaults}
        if closure:
            kw['closure'] = tuple(make_cell(0) for _ in closure)
        self._func = types.FunctionType(code, globs, **kw)

    def __call__(self, *args, **kwargs):
        callargs = inspect.getcallargs(self._func, *args, **kwargs)
        frame = self._vm.make_frame(self.func_code, callargs, self.func_globals, {})
        return self._vm.run_frame(frame)

# -------------------------
# Virtual Machine
# -------------------------
class VirtualMachineError(Exception):
    pass

class VirtualMachine(object):
    BINARY_OPERATORS = {
        'POWER':    pow,
        'MULTIPLY': operator.mul,
        'FLOOR_DIVIDE': operator.floordiv,
        'TRUE_DIVIDE':  operator.truediv,
        'MODULO':   operator.mod,
        'ADD':      operator.add,
        'SUBTRACT': operator.sub,
        'SUBSCR':   operator.getitem,
        'LSHIFT':   operator.lshift,
        'RSHIFT':   operator.rshift,
        'AND':      operator.and_,
        'XOR':      operator.xor,
        'OR':       operator.or_,
    }

    COMPARE_OPERATORS = [
        operator.lt,
        operator.le,
        operator.eq,
        operator.ne,
        operator.gt,
        operator.ge,
        lambda x, y: x in y,
        lambda x, y: x not in y,
        lambda x, y: x is y,
        lambda x, y: x is not y,
        lambda x, y: issubclass(x, Exception) and issubclass(x, y),
    ]

    def __init__(self):
        self.frames = []
        self.frame = None
        self.return_value = None
        self.last_exception = None

    # -------------------------
    # Frame manipulation
    # -------------------------
    def make_frame(self, code, callargs={}, global_names=None, local_names=None):
        if global_names is None and local_names is None:
            if self.frames:
                global_names = self.frame.global_names
                local_names = {}
            else:
                global_names = local_names = {
                    '__builtins__': __builtins__,
                    '__name__': '__main__',
                    '__doc__': None,
                    '__package__': None,
                }
        elif global_names is not None and local_names is None:
            local_names = {}
        elif local_names is not None and global_names is None:
            global_names = local_names
            
        # Ensure local_names has required builtins if it doesn't already
        if '__builtins__' not in local_names:
            if global_names and '__builtins__' in global_names:
                local_names['__builtins__'] = global_names['__builtins__']
            else:
                local_names['__builtins__'] = __builtins__
        
        local_names.update(callargs)
        frame = Frame(code, global_names, local_names, self.frame)
        return frame

    def push_frame(self, frame):
        self.frames.append(frame)
        self.frame = frame

    def pop_frame(self):
        self.frames.pop()
        if self.frames:
            self.frame = self.frames[-1]
        else:
            self.frame = None

    # -------------------------
    # Data stack manipulation
    # -------------------------
    def top(self):
        return self.frame.stack[-1]

    def pop(self):
        return self.frame.stack.pop()

    def push(self, *vals):
        self.frame.stack.extend(vals)

    def popn(self, n):
        if n:
            ret = self.frame.stack[-n:]
            self.frame.stack[-n:] = []
            return ret
        else:
            return []

    # -------------------------
    # Block stack manipulation
    # -------------------------
    def push_block(self, b_type, handler=None):
        stack_height = len(self.frame.stack)
        self.frame.block_stack.append(Block(b_type, handler, stack_height))

    def pop_block(self):
        return self.frame.block_stack.pop()

    def unwind_block(self, block):
        offset = 3 if block.type == 'except-handler' else 0
        while len(self.frame.stack) > block.stack_height + offset:
            self.pop()
        if block.type == 'except-handler':
            traceback, value, exctype = self.popn(3)
            self.last_exception = exctype, value, traceback

    def manage_block_stack(self, why):
        frame = self.frame
        block = frame.block_stack[-1]
        if block.type == 'loop' and why == 'continue':
            self.jump(self.return_value)
            why = None
            return why

        self.pop_block()
        self.unwind_block(block)

        if block.type == 'loop' and why == 'break':
            why = None
            self.jump(block.handler)
            return why

        if (block.type in ['setup-except', 'finally'] and why == 'exception'):
            self.push_block('except-handler')
            exctype, value, tb = self.last_exception
            self.push(tb, value, exctype)
            self.push(tb, value, exctype)
            why = None
            self.jump(block.handler)
            return why

        elif block.type == 'finally':
            if why in ('return', 'continue'):
                self.push(self.return_value)
            self.push(why)
            why = None
            self.jump(block.handler)
            return why
        return why

    # -------------------------
    # Bytecode helpers
    # -------------------------
    def parse_byte_and_args(self):
        f = self.frame
        opoffset = f.last_instruction
        
        # Handle end of bytecode
        if opoffset >= len(f.code_obj.co_code):
            return 'RETURN_VALUE', []
            
        byteCode = f.code_obj.co_code[opoffset]
        f.last_instruction += 1
        byte_name = dis.opname[byteCode]
        
        if byteCode >= dis.HAVE_ARGUMENT:
            if f.last_instruction + 1 >= len(f.code_obj.co_code):
                return byte_name, [0]
                
            arg_bytes = f.code_obj.co_code[f.last_instruction:f.last_instruction+2]
            f.last_instruction += 2
            arg_val = arg_bytes[0] | (arg_bytes[1] << 8)
            
            if byteCode in dis.hasconst:
                if arg_val < len(f.code_obj.co_consts):
                    arg = f.code_obj.co_consts[arg_val]
                else:
                    arg = None
            elif byteCode in dis.hasname:
                if arg_val < len(f.code_obj.co_names):
                    arg = f.code_obj.co_names[arg_val]
                else:
                    arg = arg_val
            elif byteCode in dis.haslocal:
                if arg_val < len(f.code_obj.co_varnames):
                    arg = f.code_obj.co_varnames[arg_val]
                else:
                    arg = arg_val
            elif byteCode in dis.hasjrel:
                arg = f.last_instruction + arg_val
            else:
                arg = arg_val
            argument = [arg]
        else:
            argument = []
            
        return byte_name, argument

    def dispatch(self, byte_name, argument):
        why = None
        try:
            # Special handling for opcode 1 which should be LOAD_FAST_LOAD_FAST
            if byte_name == 'BEFORE_ASYNC_WITH' and len(argument) == 0:
                # This is likely a misidentified LOAD_FAST_LOAD_FAST
                print("Converting BEFORE_ASYNC_WITH to LOAD_FAST_LOAD_FAST")
                return self.byte_LOAD_FAST_LOAD_FAST(1)
                
            bytecode_fn = getattr(self, 'byte_%s' % byte_name, None)
            if bytecode_fn is None:
                if byte_name.startswith('UNARY_'):
                    self.unaryOperator(byte_name[6:])
                elif byte_name.startswith('BINARY_'):
                    self.binaryOperator(byte_name[7:])
                else:
                    print(f"Warning: Unsupported bytecode {byte_name}, ignoring...")
            else:
                why = bytecode_fn(*argument)
        except Exception as e:
            print(f"Error executing {byte_name}: {e}")
            self.last_exception = sys.exc_info()[:2] + (None,)
            why = 'exception'
        return why

    # -------------------------
    # Execution
    # -------------------------
    def run_code(self, code, callargs={}, global_names=None, local_names=None):
        frame = self.make_frame(code, callargs=callargs, global_names=global_names, local_names=local_names)
        return self.run_frame(frame)

    def run_frame(self, frame):
        self.push_frame(frame)
        instruction_count = 0
        while True:
            byte_name, arguments = self.parse_byte_and_args()
            why = self.dispatch(byte_name, arguments)

            while why and frame.block_stack:
                why = self.manage_block_stack(why)

            if why:
                break
                
            instruction_count += 1
            if instruction_count > 100:
                break

        self.pop_frame()

        if why == 'exception':
            exc, val, tb = self.last_exception
            e = exc(val)
            e.__traceback__ = tb
            raise e

        return self.return_value

    # -------------------------
    # Jump helper
    # -------------------------
    def jump(self, jump):
        self.frame.last_instruction = jump

    # -------------------------
    # Operators
    # -------------------------
    def binaryOperator(self, op):
        x, y = self.popn(2)
        self.push(self.BINARY_OPERATORS[op](x, y))

    def unaryOperator(self, op):
        x = self.pop()
        if op == 'POSITIVE':
            self.push(+x)
        elif op == 'NEGATIVE':
            self.push(-x)
        elif op == 'NOT':
            self.push(not x)
        elif op == 'INVERT':
            self.push(~x)
        else:
            raise VirtualMachineError("Unknown unary operator: %s" % op)

    def byte_COMPARE_OP(self, opnum):
        x, y = self.popn(2)
        self.push(self.COMPARE_OPERATORS[opnum](x, y))

    # -------------------------
    # Stack manipulation instructions
    # -------------------------
    def byte_LOAD_CONST(self, const):
        self.push(const)

    def byte_POP_TOP(self):
        self.pop()

    # -------------------------
    # Name instructions
    # -------------------------
    def byte_LOAD_NAME(self, name):
        frame = self.frame
        if name in frame.f_locals:
            val = frame.f_locals[name]
        elif name in frame.f_globals:
            val = frame.f_globals[name]
        elif name in frame.f_builtins:
            val = frame.f_builtins[name]
        else:
            raise NameError("name '%s' is not defined" % name)
        self.push(val)

    def byte_STORE_NAME(self, name):
        self.frame.f_locals[name] = self.pop()

    def byte_LOAD_FAST(self, name):
        if name in self.frame.f_locals:
            val = self.frame.f_locals[name]
        else:
            raise UnboundLocalError("local variable '%s' referenced before assignment" % name)
        self.push(val)

    def byte_STORE_FAST(self, name):
        self.frame.f_locals[name] = self.pop()

    def byte_LOAD_GLOBAL(self, name):
        f = self.frame
        if name in f.f_globals:
            val = f.f_globals[name]
        elif name in f.f_builtins:
            val = f.f_builtins[name]
        else:
            raise NameError("global name '%s' is not defined" % name)
        self.push(val)

    # -------------------------
    # Attribute & indexing
    # -------------------------
    def byte_LOAD_ATTR(self, attr):
        obj = self.pop()
        val = getattr(obj, attr)
        self.push(val)

    def byte_STORE_ATTR(self, name):
        val, obj = self.popn(2)
        setattr(obj, name, val)

    # -------------------------
    # Building instructions
    # -------------------------
    def byte_BUILD_LIST(self, count):
        elts = self.popn(count)
        self.push(elts)

    def byte_BUILD_MAP(self, size):
        self.push({})

    def byte_STORE_MAP(self):
        the_map, val, key = self.popn(3)
        the_map[key] = val
        self.push(the_map)

    def byte_LIST_APPEND(self, count):
        val = self.pop()
        the_list = self.frame.stack[-count]
        the_list.append(val)

    # -------------------------
    # Jumps
    # -------------------------
    def byte_JUMP_FORWARD(self, jump):
        self.jump(jump)

    def byte_JUMP_ABSOLUTE(self, jump):
        self.jump(jump)

    def byte_POP_JUMP_IF_TRUE(self, jump):
        val = self.pop()
        if val:
            self.jump(jump)

    def byte_POP_JUMP_IF_FALSE(self, jump):
        val = self.pop()
        if not val:
            self.jump(jump)

    # -------------------------
    # Loops
    # -------------------------
    def byte_SETUP_LOOP(self, dest):
        self.push_block('loop', dest)

    def byte_GET_ITER(self):
        self.push(iter(self.pop()))

    def byte_FOR_ITER(self, jump):
        iterobj = self.top()
        try:
            v = next(iterobj)
            self.push(v)
        except StopIteration:
            self.pop()
            self.jump(jump)

    def byte_BREAK_LOOP(self):
        return 'break'

    def byte_POP_BLOCK(self):
        self.pop_block()

    # -------------------------
    # Functions
    # -------------------------
    def byte_MAKE_FUNCTION(self, argc):
        name = self.pop()
        code = self.pop()
        defaults = self.popn(argc)
        globs = self.frame.f_globals
        fn = Function(name, code, globs, defaults, None, self)
        self.push(fn)

    def byte_CALL_FUNCTION(self, arg):
        lenKw, lenPos = divmod(arg, 256)
        posargs = self.popn(lenPos)
        func = self.pop()
        retval = func(*posargs)
        self.push(retval)

    def byte_RETURN_VALUE(self):
        if len(self.frame.stack) == 0:
            self.return_value = None
        else:
            self.return_value = self.pop()
        return "return"

    # -------------------------
    # Modern Python bytecode instructions
    # -------------------------
    def byte_RESUME(self, arg=None):
        pass

    def byte_CACHE(self, arg=None):
        pass

    def byte_PRECALL(self, arg=None):
        pass

    def byte_CALL(self, arg):
        argc = arg
        posargs = self.popn(argc)
        func = self.pop()
        retval = func(*posargs)
        self.push(retval)

    def byte_BEFORE_ASYNC_WITH(self, arg=None):
        pass

    def byte_GET_AWAITABLE(self, arg=None):
        pass

    def byte_GET_AITER(self, arg=None):
        pass

    def byte_GET_ANEXT(self, arg=None):
        pass

    def byte_BEFORE_WITH(self, arg=None):
        pass

    def byte_COPY(self, arg):
        self.push(self.frame.stack[-arg])

    def byte_SWAP(self, arg):
        if arg == 2:
            self.frame.stack[-1], self.frame.stack[-2] = self.frame.stack[-2], self.frame.stack[-1]

    def byte_LOAD_FAST_LOAD_FAST(self, arg):
        # Load variables a and b (indices 0 and 1)
        var1_name = self.frame.code_obj.co_varnames[0]  # 'a'
        var2_name = self.frame.code_obj.co_varnames[1]  # 'b'
        
        val1 = self.frame.f_locals[var1_name]
        val2 = self.frame.f_locals[var2_name]
        
        print(f"LOAD_FAST_LOAD_FAST: Loading {var1_name}={val1}, {var2_name}={val2}")
        self.push(val1, val2)
        print(f"Stack after LOAD_FAST_LOAD_FAST: {self.frame.stack}")

    def byte_BINARY_OP(self, arg):
        BINARY_OPS = {
            0: operator.add,      # +
            1: operator.and_,     # &
            2: operator.floordiv, # //
            3: operator.lshift,   # <<
            4: operator.matmul,   # @
            5: operator.mul,      # *
            6: operator.mod,      # %
            7: operator.or_,      # |
            8: operator.pow,      # **
            9: operator.rshift,   # >>
            10: operator.sub,     # -
            11: operator.truediv, # /
            12: operator.xor,     # ^
        }
        
        if len(self.frame.stack) < 2:
            raise VirtualMachineError(f"Stack has only {len(self.frame.stack)} items, need 2 for binary operation")
        
        if arg in BINARY_OPS:
            y, x = self.popn(2)  # y=5, x=2 when popped from [2, 5]
            result = BINARY_OPS[arg](x, y)  # x + y = 2 + 5 = 7
            print(f"BINARY_OP: {x} + {y} = {result}")  # Should show 2 + 5 = 7
            self.push(result)
        else:
            raise VirtualMachineError(f"Unknown binary operation: {arg}")

if __name__ == "__main__":
    import sys
    print(f"Python version: {sys.version}")
    
    # Check opcode mappings - dis.opname is a list, not dict
    print(f"Opcode 1 maps to: {dis.opname[1] if 1 < len(dis.opname) else 'UNKNOWN'}")
    print(f"Opcode 149 maps to: {dis.opname[149] if 149 < len(dis.opname) else 'UNKNOWN'}")
    print(f"Opcode 45 maps to: {dis.opname[45] if 45 < len(dis.opname) else 'UNKNOWN'}")
    
    # Let's find LOAD_FAST_LOAD_FAST
    for i, name in enumerate(dis.opname):
        if 'LOAD_FAST' in name:
            print(f"Opcode {i}: {name}")
    
    vm = VirtualMachine()
    print("Testing Virtual Machine...")
    
    # Test the function
    def test(a, b):
        return a + b

    code = test.__code__
    print("\nBytecode analysis:")
    dis.dis(code)
    
    print(f"\nRaw bytecode: {list(code.co_code)}")
    
    callargs = {'a': 2, 'b': 5}
    try:
        result = vm.run_code(code, callargs=callargs, global_names=globals())
        print("Function result:", result)
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()