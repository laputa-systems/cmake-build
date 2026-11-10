# Initial CMake performance analysis

This analysis describes the x86-64 prerelease at commit `58313ac`. The
[measurements and raw samples](performance.md) use ten interleaved repetitions
because that run was already in progress when the owner set the future minimum
to five. The four-CPU run shared the host with other work. The one-minute host
load at sample boundaries ranged from 1.91 to 5.11 on eight logical CPUs.
Cold-cache behavior was not measured.
The clean and incremental cost of building CMake itself was not measured in
this run. Laputa provisioning and consumer builds also remain unmeasured.

The shipped binary has no demonstrated configure-time advantage over the
unmodified static-musl baseline in these workloads. For fmt's initial
configuration, their medians were 0.442 and 0.441 seconds. Their observed
ranges were 0.413–0.498 and 0.397–0.491 seconds. For LLVM with Clang, initial
configuration medians were 30.102 and 29.914 seconds, with ranges of
29.280–31.464 and 28.931–31.849 seconds. These ranges overlap. The comparison
also includes the product's Rustls and patch differences; it does not isolate
an individual compiler flag.

Kitware's glibc binary recorded an LLVM unchanged-reconfigure median of
15.904 seconds, compared with 18.127 seconds for the product. The binaries use
different runtimes and bundled resources. This external comparison does not
identify the cause. The container lacked Git during LLVM configuration, and
all variants used the same pinned Alpine Python and LLVM/musl toolchain.

The untimed product trace of LLVM unchanged reconfiguration included 241,126
`stat`, 117,306 `lstat`, and 150,759 `readlink` calls across the traced process
tree. It also recorded 51 `execve` and 62 `wait4` calls. The corresponding
musl baseline trace recorded the same counts for those calls. This identifies
filesystem metadata and subprocess activity to investigate. Aggregate tracing
includes child processes, adds overhead, and cannot attribute those calls to
CMake itself or establish their share of normal wall time.

The host has no `perf` executable, so this initial run did not include CPU
sampling. A later [main-thread CPU profile](profiles/llvm-reconfigure.md) used
the kernel perf-event interface directly. Parsing, allocation, compiler
discovery, executor work, and filesystem effects are not separately ranked by
the initial results. Do not infer a CMake runtime speedup from
the debug-stripping size reduction. The current data support keeping the
simpler compiler flags until an isolated candidate demonstrates a gain beyond
observed variation. The subsequent [Rustls release-profile study](performance-rust-release.md)
measured a smaller executable without a clear runtime change.

The qualified CMake build uses upstream `Release` defaults for C and C++:
`-O3 -DNDEBUG`. Its linker flags retain static PIE, RELRO, immediate
binding, and a non-executable stack. Curses and Qt dialogs are disabled. The
build still produces CTest and upstream test helpers for qualification; Ninja's
default `Source/all` also builds CPack, although `libCPackLib` is absent from
the shipped CMake link map and CPack is not packaged. Removing that build-only
target would not by itself improve the shipped executable. O2, size-oriented
optimization, ThinLTO, identical-code folding, and section garbage collection
were not measured in this study; the available profile does not establish a
specific safe change among them.
