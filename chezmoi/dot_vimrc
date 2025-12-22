if 0 | endif

" NeoBundle 'vim-airline/vim-airline'
" NeoBundle 'vim-airline/vim-airline-themes'
" NeoBundle 'NLKNguyen/papercolor-theme'
" NeoBundle 'tpope/vim-fireplace'
" NeoBundle 'dodie/vim-disapprove-deep-indentation'
" NeoBundle 'ervandew/supertab'
" NeoBundle 'mtth/scratch.vim'
" NeoBundle 'bhurlow/vim-parinfer'
" NeoBundle 'sjl/gundo.vim'
" NeoBundle 'Shougo/neosnippet.vim'
" NeoBundle 'Shougo/neosnippet-snippets'
" NeoBundle 'tpope/vim-fugitive'
" NeoBundle 'ctrlpvim/ctrlp.vim'
" NeoBundle 'flazz/vim-colorschemes'
" NeoBundle 'Shougo/vimshell'

let mapleader=","
nnoremap <leader>a :echo("\<leader\> works! It is set to <leader>")<CR>
" nnoremap <C-a> :echo("\<leader\> works! It is set to <leader>")<CR>
noremap <silent> <expr> j (v:count == 0 ? 'gj' : 'j')
noremap <silent> <expr> k (v:count == 0 ? 'gk' : 'k')
" move to beginning/end of line
nnoremap B ^
nnoremap E $
nnoremap <leader>u :GundoToggle<CR>
" Quickly select the text that was just pasted. This allows you to, e.g.,
" indent it after pasting.
noremap gV `[v`]
" Make Y yank everything from the cursor to the end of the line. This makes Y
" act more like C or D because by default, Y yanks the current line (i.e.
" the same as yy).
noremap Y y$
" Make Ctrl-e jump to the end of the current line in the insert mode. This is
" handy when you are in the middle of a line and would like to go to its end
" without switching to the normal mode.
inoremap <C-e> <C-o>$
" Make Ctrl-a jump to the beginning of the current line in the insert mode. This is
" handy when you are in the middle of a line and would like to go to its beginning
" without switching to the normal mode.
inoremap <C-a> <C-o>^
nnoremap <silent> <leader>3 :setl nonumber! norelativenumber!<CR>
" turn off search highlighting
nnoremap <leader><space> :nohlsearch<CR>
" previous tab with ctrl-left
nnoremap <C-Left> :tabprevious<CR>
" next tab with ctrl-right
nnoremap <C-Right> :tabnext<CR>

" General config
syntax on " enable syntax processing
set autoindent
set hidden
set incsearch " search as characters are entered
set hlsearch " highlight matches
set backspace=indent,eol,start
set tabstop=2 " # of visual spaces per TAB
set softtabstop=2 " # of spaces inserted when hitting <TAB>
set shiftwidth=2 " # of spaces to indent automatically
set expandtab " tabs are spaces
set number " show line numbers
set relativenumber " show line numbers relative to cursor
set pastetoggle=<C-v>
set laststatus=2
set wildmenu " visual autocomplete in command menu
set lazyredraw "redraw only when we need to
set backup
set backupdir=~/.vim-tmp,~/.tmp,/var/tmp,/tmp
set backupskip=/tmp*,/private/tmp*
set directory=~/.vim-tmp,~/.tmp,~/tmp,/var/tmp,/tmp
set writebackup

" taken from here: https://www.johnhawthorn.com/2012/09/vi-escape-delays/
" this will make esc change the state immediately instead of waiting a second
" first
set timeoutlen=1000 ttimeoutlen=0
" resource vimrc file
augroup myvimrchooks
    au!
    autocmd bufwritepost .vimrc source ~/.vimrc
augroup END
" reopen file to same line
" if has("autocmd")
"   au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g'\"" | endif
" endif

" Plugin configs
" Papercolor
let g:airline_theme='papercolor'
let g:lightline = { 'colorscheme': 'PaperColor' }

" scala-vim
let g:scala_scaladoc_indent = 1

" clojure settings

" pane settings
nnoremap <C-H> <C-W><Left>
nnoremap <C-L> <C-W><Right>
nnoremap <C-J> <C-W><Down>
nnoremap <C-K> <C-W><Up>
set splitbelow
set splitright

" Terminal fixes
"
" These originate from some linux distribution's system vimrc. I can't say
" that I understand the details what's going on here, but without these
" settings, I've had problems like vim starting in REPLACE mode for
" TERM=xterm-256color (neovim is fine)

if &term =~? 'xterm'
    let s:myterm = 'xterm'
else
    let s:myterm =  &term
endif
let s:myterm = substitute(s:myterm, 'cons[0-9][0-9].*$',  'linux', '')
let s:myterm = substitute(s:myterm, 'vt1[0-9][0-9].*$',   'vt100', '')
let s:myterm = substitute(s:myterm, 'vt2[0-9][0-9].*$',   'vt220', '')
let s:myterm = substitute(s:myterm, '\\([^-]*\\)[_-].*$', '\\1',   '')

" Here we define the keys of the NumLock in keyboard transmit mode of xterm
" which misses or hasn't activated Alt/NumLock Modifiers.  Often not defined
" within termcap/terminfo and we should map the character printed on the keys.
if s:myterm ==? 'xterm' || s:myterm ==? 'kvt' || s:myterm ==? 'gnome'
    " keys in insert/command mode.
    map! <ESC>Oo  :
    map! <ESC>Oj  *
    map! <ESC>Om  -
    map! <ESC>Ok  +
    map! <ESC>Ol  ,
"    map! <ESC>OM  
    map! <ESC>Ow  7
    map! <ESC>Ox  8
    map! <ESC>Oy  9
    map! <ESC>Ot  4
    map! <ESC>Ou  5
    map! <ESC>Ov  6
    map! <ESC>Oq  1
    map! <ESC>Or  2
    map! <ESC>Os  3
    map! <ESC>Op  0
    map! <ESC>On  .
    " keys in normal mode
    map <ESC>Oo  :
    map <ESC>Oj  *
    map <ESC>Om  -
    map <ESC>Ok  +
    map <ESC>Ol  ,
"    map <ESC>OM  
    map <ESC>Ow  7
    map <ESC>Ox  8
    map <ESC>Oy  9
    map <ESC>Ot  4
    map <ESC>Ou  5
    map <ESC>Ov  6
    map <ESC>Oq  1
    map <ESC>Or  2
    map <ESC>Os  3
    map <ESC>Op  0
    map <ESC>On  .
endif

" xterm but without activated keyboard transmit mode
" and therefore not defined in termcap/terminfo.
if s:myterm ==? 'xterm' || s:myterm ==? 'kvt' || s:myterm ==? 'gnome'
    " keys in insert/command mode.
    map! <Esc>[H  <Home>
    map! <Esc>[F  <End>
    " Home/End: older xterms do not fit termcap/terminfo.
    map! <Esc>[1~ <Home>
    map! <Esc>[4~ <End>
    " Up/Down/Right/Left
    map! <Esc>[A  <Up>
    map! <Esc>[B  <Down>
    map! <Esc>[C  <Right>
    map! <Esc>[D  <Left>
    " KP_5 (NumLock off)
    map! <Esc>[E  <Insert>
    " PageUp/PageDown
    map <ESC>[5~ <PageUp>
    map <ESC>[6~ <PageDown>
    map <ESC>[5;2~ <PageUp>
    map <ESC>[6;2~ <PageDown>
    map <ESC>[5;5~ <PageUp>
    map <ESC>[6;5~ <PageDown>
    " keys in normal mode
    map <ESC>[H  0
    map <ESC>[F  $
    " Home/End: older xterms do not fit termcap/terminfo.
    map <ESC>[1~ 0
    map <ESC>[4~ $
    " Up/Down/Right/Left
    map <ESC>[A  k
    map <ESC>[B  j
    map <ESC>[C  l
    map <ESC>[D  h
    " KP_5 (NumLock off)
    map <ESC>[E  i
    " PageUp/PageDown
    map <ESC>[5~ 
    map <ESC>[6~ 
    map <ESC>[5;2~ 
    map <ESC>[6;2~ 
    map <ESC>[5;5~ 
    map <ESC>[6;5~ 
endif

" xterm/kvt but with activated keyboard transmit mode.
" Sometimes not or wrong defined within termcap/terminfo.
if s:myterm ==? 'xterm' || s:myterm ==? 'kvt' || s:myterm ==? 'gnome'
    " keys in insert/command mode.
    map! <Esc>OH <Home>
    map! <Esc>OF <End>
    map! <ESC>O2H <Home>
    map! <ESC>O2F <End>
    map! <ESC>O5H <Home>
    map! <ESC>O5F <End>
    " Cursor keys which works mostly
    " map! <Esc>OA <Up>
    " map! <Esc>OB <Down>
    " map! <Esc>OC <Right>
    " map! <Esc>OD <Left>
    map! <Esc>[2;2~ <Insert>
    map! <Esc>[3;2~ <Delete>
    map! <Esc>[2;5~ <Insert>
    map! <Esc>[3;5~ <Delete>
    map! <Esc>O2A <PageUp>
    map! <Esc>O2B <PageDown>
    map! <Esc>O2C <S-Right>
    map! <Esc>O2D <S-Left>
    map! <Esc>O5A <PageUp>
    map! <Esc>O5B <PageDown>
    map! <Esc>O5C <S-Right>
    map! <Esc>O5D <S-Left>
    " KP_5 (NumLock off)
    map! <Esc>OE <Insert>
    " keys in normal mode
    map <ESC>OH  0
    map <ESC>OF  $
    map <ESC>O2H  0
    map <ESC>O2F  $
    map <ESC>O5H  0
    map <ESC>O5F  $
    " Cursor keys which works mostly
    " map <ESC>OA  k
    " map <ESC>OB  j
    " map <ESC>OD  h
    " map <ESC>OC  l
    map <Esc>[2;2~ i
    map <Esc>[3;2~ x
    map <Esc>[2;5~ i
    map <Esc>[3;5~ x
    map <ESC>O2A  ^B
    map <ESC>O2B  ^F
    map <ESC>O2D  b
    map <ESC>O2C  w
    map <ESC>O5A  ^B
    map <ESC>O5B  ^F
    map <ESC>O5D  b
    map <ESC>O5C  w
    " KP_5 (NumLock off)
    map <ESC>OE  i
endif

if s:myterm ==? 'linux'
    " keys in insert/command mode.
    map! <Esc>[G  <Insert>
    " KP_5 (NumLock off)
    " keys in normal mode
    " KP_5 (NumLock off)
    map <ESC>[G  i
endif

" This escape sequence is the well known ANSI sequence for
" Remove Character Under The Cursor (RCUTC[tm])
map! <Esc>[3~ <Delete>
map  <ESC>[3~    x
