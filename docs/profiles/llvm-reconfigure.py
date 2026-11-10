import os

cpus = sorted(os.sched_getaffinity(0))[:4]
os.sched_setaffinity(0, cpus)
command = ['/variants/product/bin/cmake', '-S', '/benchmark/product/llvm-clang/source/llvm',
           '-B', '/benchmark/product/llvm-clang/build', '-G', 'Ninja',
           '-DCMAKE_MAKE_PROGRAM=/tools/ninja', '-DCMAKE_TOOLCHAIN_FILE=/tools/toolchain.cmake',
           '-DCMAKE_BUILD_TYPE=Release', '-DLLVM_ENABLE_PROJECTS=clang',
           '-DPython3_EXECUTABLE=/opt/alpine/usr/python3', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON']
os.execv(command[0], command)
