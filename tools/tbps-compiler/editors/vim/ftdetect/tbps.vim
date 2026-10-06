" Filetype detection for ROB3 TBPS teach-box programs.
" Installs the 'tbps' filetype for *.tbps files (and *.tb, used by some tools).
au BufRead,BufNewFile *.tbps set filetype=tbps
au BufRead,BufNewFile *.tb   set filetype=tbps
