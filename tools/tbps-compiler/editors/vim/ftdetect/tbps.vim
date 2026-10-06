" Filetype detection for ROB3 TBPS teach-box programs.
" Primary source extension: .tbps ; aliases: .tb, .dat (original TBPS convention).
" NOTE: .dat is intentionally mapped too, but it is a generic extension — if it
" clashes with other .dat files in your projects, drop the .dat line below.
au BufRead,BufNewFile *.tbps set filetype=tbps
au BufRead,BufNewFile *.tb   set filetype=tbps
au BufRead,BufNewFile *.dat  set filetype=tbps
