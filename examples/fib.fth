: fib ( n -- a )
   1 0 rot 0 do over + swap loop
;

10 fib . cr bye
