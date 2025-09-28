# **ByteRun: A Python Virtual Machine**

**ByteRun** is a Python Virtual Machine (VM) implementation written in Python, designed to execute Python bytecode in a controlled environment. It supports modern Python 3.13 bytecode instructions, including `RESUME`, `BINARY_OP`, `LOAD_FAST_LOAD_FAST`, and more. This project can be used for learning how Python executes code under the hood, debugging bytecode, or experimenting with custom Python VMs.

---

## **Table of Contents**

- [Features](#features)  
- [Installation](#installation)  
- [Usage](#usage)  
- [Supported Instructions](#supported-instructions)  
- [Project Structure](#project-structure)   
- [Contributing](#contributing)  

---

## **Features**

- Custom implementation of a Python Virtual Machine from scratch.  
- Supports Python 3.13 bytecode instructions including arithmetic, function calls, and variable handling.  
- Handles binary operations, unary operations, and modern opcodes like `RESUME`.  
- Allows frame creation, local/global variable management, and function execution.  
- Includes detailed debug print statements for understanding stack and bytecode execution.  

---

## **Installation**

1. **Clone the repository:**

```bash
git clone https://github.com/<your-username>/ByteRun.git
```
2. **Navigate into the Project directory**

```bash
cd ByteRun
```

---

## **Usage**

1. **Run the main VM**

```bash
python byterun.py
```

2. **Example: Running a function with the VM**

```python
from byterun import VirtualMachine

vm = VirtualMachine()

def add(a, b):
    return a + b

result = vm.run_code(add.__code__, callargs={'a': 2, 'b': 5})
print(result)  # Output: 7
```

3. **Testing your own functions**

Open `byterun.py` and add your Python function to test at the bottom of the file under:

```python
if __name__ == "__main__":
    # your test function here
```

Then run:

```bash
python byterun.py
```

4. **Running multople test cases**
Use **test.py** for batch testing and debugging:

```bash
python test.py
```
Observe the debug output to understand bytecode execution, stack operations, and final results.

---

## **Supported Instructions**

- **Stack operations:** `LOAD_CONST`, `POP_TOP`, `LOAD_FAST`, `STORE_FAST`, `LOAD_GLOBAL`, `STORE_NAME`, `LOAD_NAME`

- **Binary operations:** `BINARY_OP`

- **Unary operations:** `UNARY_POSITIVE`, `UNARY_NEGATIVE`, `UNARY_NOT`, `UNARY_INVERT`

- **Function operations:** `MAKE_FUNCTION`, `CALL_FUNCTION`, `RETURN_VALUE`

- **Attribute operations:** `LOAD_ATTR`, `STORE_ATTR`

- **Collection operations:** `BUILD_LIST`, `BUILD_MAP`, `STORE_MAP`, `LIST_APPEND`

- **Control flow operations:** `JUMP_FORWARD`, `JUMP_ABSOLUTE`, `POP_JUMP_IF_TRUE`, `POP_JUMP_IF_FALSE`, `SETUP_LOOP`, `GET_ITER`, `FOR_ITER`, `BREAK_LOOP`, `POP_BLOCK`

- *8Modern Python 3.13 opcodes:** `RESUME`, `LOAD_FAST_LOAD_FAST`, `BEFORE_ASYNC_WITH`, `PRECALL`, `CALL`, `GET_AWAITABLE`, `GET_AITER`, `GET_ANEXT`, `COPY`, `SWAP`

---

## **Project Structure**

```t
ByteRun/
│
├── byterun.py          # Main VM implementation
├── README.md           # This documentation
├── .gitignore          # Recommended to ignore __pycache__, venv, etc.
└── test.py             # Folder for unit tests
```

---

## **Contributing**

1. Fork the repository.

2. Create a new branch:

```bash
git checkout -b feature/my-feature
```

3. Commit your changes:

```bash
git commit -am 'Add new feature'
```

4. Push to the branch:

```bash
git push origin feature/my-feature
```

5. Create a Pull request.

---

**Acknowledgments**

- Python community for insights into bytecode and interpreter design

- Open-source projects and tutorials on virtual machines and Python internals

- Developers who contribute to educational resources for understanding Python execution

**Support**
If you encounter any issues or have questions, please:

- Check the existing issues on the ByteRun GitHub repository

- Create a new issue with detailed information

- Include sample code, bytecode, or steps to reproduce the problem

---

Thank you for checking out ByteRun! Your contributions, suggestions, and feedback are always welcome. 🚀