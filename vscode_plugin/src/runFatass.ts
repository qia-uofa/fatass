import * as vscode from "vscode";

let terminal: vscode.Terminal | undefined;

function getTerminal(cwd: string): vscode.Terminal {
  if (!terminal || terminal.exitStatus !== undefined) {
    terminal = vscode.window.createTerminal({ name: "fatass", cwd });
  }
  return terminal;
}

/** Runs `python -m fatass <args...>` in a shared integrated terminal. */
export function runFatass(cwd: string, args: string[]): void {
  const t = getTerminal(cwd);
  t.show();
  const quoted = args.map((a) => (/\s/.test(a) ? `"${a}"` : a));
  t.sendText(`python -m fatass ${quoted.join(" ")}`);
}
