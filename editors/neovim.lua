-- OpenLattice LSP configuration for Neovim
-- Requires: nvim-lspconfig (https://github.com/neovim/nvim-lspconfig)
-- Install the LSP server: pip install openlattice[lsp]
--
-- Add this snippet to your Neovim config (init.lua or a dedicated lsp.lua file).

local lspconfig = require('lspconfig')
local configs = require('lspconfig.configs')

-- Register openlattice as a custom LSP server if not already known
if not configs.openlattice then
  configs.openlattice = {
    default_config = {
      cmd = { 'openlattice-lsp' },
      filetypes = { 'lattice' },
      root_dir = lspconfig.util.root_pattern('.git', '*.lattice'),
      single_file_support = true,
    },
    docs = {
      description = 'OpenLattice language server for .lattice declarative app-spec files.',
    },
  }
end

-- Tell Neovim about the .lattice filetype
vim.filetype.add({
  extension = {
    lattice = 'lattice',
  },
})

-- Start the server for lattice files
lspconfig.openlattice.setup({
  -- Optional: pass capabilities from nvim-cmp or similar
  -- capabilities = require('cmp_nvim_lsp').default_capabilities(),
  on_attach = function(client, bufnr)
    -- Enable completion triggered by <C-x><C-o>
    vim.bo[bufnr].omnifunc = 'v:lua.vim.lsp.omnifunc'

    local opts = { buffer = bufnr, silent = true }
    vim.keymap.set('n', 'K',          vim.lsp.buf.hover,          opts)
    vim.keymap.set('n', '<leader>ca', vim.lsp.buf.code_action,    opts)
    vim.keymap.set('n', ']d',         vim.diagnostic.goto_next,   opts)
    vim.keymap.set('n', '[d',         vim.diagnostic.goto_prev,   opts)
  end,
})
