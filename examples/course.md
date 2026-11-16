# A tiny course, checked by cobaye

Integer division truncates toward zero in C:

```c
#include <stdio.h>
int main(void) { printf("%d %d\n", 7 / 2, -7 / 2); return 0; }
```

```output
3 -3
```

In OCaml, `List.fold_left` goes from the left:

```ocaml
List.fold_left (fun acc x -> acc * 10 + x) 0 [1; 2; 3];;
```

```output
- : int = 123
```

Python slices never fail on out-of-range bounds:

```python
print([1, 2, 3][1:10])
```

```output
[2, 3]
```

This one is wrong on purpose (a classic mistake about `sizeof` on a pointer):

```c
#include <stdio.h>
void f(int t[10]) { printf("%zu\n", sizeof(t) / sizeof(t[0])); }
int main(void) { int t[10]; f(t); return 0; }
```

```output
10
```
