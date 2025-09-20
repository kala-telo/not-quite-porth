16 constant C

variable b C 1- cells allot
variable d C 1- cells allot
d C cells 0 fill

create r 0 , 1 , 1 , 1 , 0 , 1 , 1 , 0 ,

: step ( -- )
    C 0 do
        i cells d + @
        dup
        i cells b + !
        0 = if ."  " else ." #" then
    loop
    cr
    C 0 do
        i 1- C + C mod cells b + @
        i              cells b + @
        i 1+     C mod cells b + @
        swap rot 2 * + 2 * +
        cells r + @
        i cells d + !
    loop
;

: main ( -- )
    1 d C 1- cells + !
    C 1- 0 do
        step
    loop
;

main bye
