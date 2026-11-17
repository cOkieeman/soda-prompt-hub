The committed React host bundle is rebuilt with `npm ci --ignore-scripts` followed
by `npm run build` from this directory. The lock file pins React, ReactDOM and
esbuild. The host does not download JavaScript at runtime. Keep the accompanying
`agent_react.LICENSE.txt` in the web assets directory when updating dependencies.
