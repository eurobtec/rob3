" Vim syntax file for the ROB3 Teach Box Programming System (TBPS) language.
" Language:   TBPS (ROB3 / ROB3i teach-box control programs)
" Maintainer: ROB3 reverse-engineering project (tools/tbps-compiler)
" Usage:      see ../README.md ("Editor support") for installation.

if exists("b:current_syntax")
  finish
endif

" Comments: ';' or '#' to end of line (compiler extension).
syn match   tbpsComment "\v(;|#).*$" contains=tbpsTodo
syn keyword tbpsTodo    contained TODO FIXME XXX NOTE

" Program-structure commands (header / end / separators / mode).
syn keyword tbpsStructure STOP INS DEL CLR

" Instruction mnemonics.
syn keyword tbpsInstr   MARK POS TIM GOTO IF OUT NOP nextgroup=tbpsNumber skipwhite

" The ENTER terminator (ignored by the compiler but valid in source).
syn keyword tbpsEnt     ENT

" Set/clear and direction operators.
syn match   tbpsOperator "\v[+-]"

" The '.' parameter separator.
syn match   tbpsSep     "\."

" Numbers: hex (0x..) and decimal.
syn match   tbpsNumber  "\v<0x[0-9A-Fa-f]+>"
syn match   tbpsNumber  "\v<\d+>"

" Highlight links.
hi def link tbpsComment    Comment
hi def link tbpsTodo       Todo
hi def link tbpsStructure  PreProc
hi def link tbpsInstr      Statement
hi def link tbpsEnt        Special
hi def link tbpsOperator   Operator
hi def link tbpsSep        Delimiter
hi def link tbpsNumber     Number

let b:current_syntax = "tbps"
