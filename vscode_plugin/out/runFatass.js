"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isInShellRepl = isInShellRepl;
exports.fatassCommandLine = fatassCommandLine;
exports.runFatass = runFatass;
const vscode = require("vscode");
/** Terminals currently sitting inside `fatass shell`'s own REPL -- a
 * long-running "python -m fatass shell" process reading one command per
 * line from stdin, with no "python -m fatass" prefix on each line (see
 * CLAUDE.md's shell section). Tracked for every terminal, not just one we
 * created ourselves -- shell integration reports a REPL the user typed
 * directly into a terminal the same way it reports one we launched: one
 * execution that doesn't end until the REPL itself exits. A `WeakSet`
 * needs no explicit cleanup when a terminal closes. */
const replTerminals = new WeakSet();
function looksLikeShellInvocation(commandLine) {
    return /(^|[\\/])python(?:\.exe)?\b.*-m\s+fatass\s+shell(\s|$)/.test(commandLine);
}
vscode.window.onDidStartTerminalShellExecution((e) => {
    if (looksLikeShellInvocation(e.execution.commandLine.value)) {
        replTerminals.add(e.terminal);
    }
});
vscode.window.onDidEndTerminalShellExecution((e) => {
    if (looksLikeShellInvocation(e.execution.commandLine.value)) {
        replTerminals.delete(e.terminal);
    }
});
/** Whether `terminal` (default: whichever terminal is currently active) is
 * sitting inside `fatass shell`'s own REPL. Lets a caller that already
 * knows what a dispatched `cd` targets (e.g. the Topology view's own "cd"
 * command) mirror it directly instead of relying on a `.fatass/.env`
 * change that the REPL's own `cd` deliberately never produces. */
function isInShellRepl(terminal) {
    const t = terminal ?? vscode.window.activeTerminal;
    return !!t && replTerminals.has(t);
}
function quoteArgs(args) {
    return args.map((a) => (/\s/.test(a) ? `"${a}"` : a)).join(" ");
}
/** The exact `python -m fatass ...` line `runFatass` will send -- shown to
 * the user for confirmation before it actually runs. Always the full,
 * canonical form (regardless of whether the target terminal is in the
 * REPL) since this is a human-facing description of the action, not
 * necessarily what literally gets typed into the terminal. */
function fatassCommandLine(args) {
    return `python -m fatass ${quoteArgs(args)}`;
}
function runInTerminal(t, commandLine, onDone) {
    const runWithIntegration = (shellIntegration) => {
        const execution = shellIntegration.executeCommand(commandLine);
        if (onDone) {
            const sub = vscode.window.onDidEndTerminalShellExecution((e) => {
                if (e.execution === execution) {
                    sub.dispose();
                    onDone();
                }
            });
        }
    };
    if (t.shellIntegration) {
        runWithIntegration(t.shellIntegration);
        return;
    }
    if (onDone) {
        const sub = vscode.window.onDidChangeTerminalShellIntegration((e) => {
            if (e.terminal === t) {
                sub.dispose();
                runWithIntegration(e.shellIntegration);
            }
        });
        // Shell integration may never activate (disabled setting, unsupported
        // shell); give up waiting for it after a while so the listener doesn't
        // leak forever.
        setTimeout(() => sub.dispose(), 10000);
    }
    t.sendText(commandLine);
}
/**
 * Runs `python -m fatass <args...>` in whichever integrated terminal is
 * currently active -- or, if that terminal is sitting inside `fatass
 * shell`'s own REPL, sends just `<args...>` on its own, since the REPL
 * reads one command per line with no "python -m fatass" prefix. Falls
 * back to creating a terminal only if none is active at all.
 *
 * `shell` itself is the one exception: running "fatass shell" *inside* an
 * existing REPL (or reusing whatever terminal happens to be active) makes
 * no sense, so it always opens a brand-new terminal instead, shown to the
 * user since that's the whole point of the command.
 *
 * Every other command deliberately never reveals/focuses the terminal's
 * panel (no `.show()`) -- a context-menu command shouldn't toggle the
 * panel open on every invocation; it stays wherever it already was, and
 * its output is there to check if/when the user opens it themselves.
 * If shell integration is available, `onDone` fires once the command's
 * shell execution actually ends (so callers can refresh views after a
 * real fatass command completes rather than immediately on dispatch).
 * Without shell integration -- or while inside the REPL, where a single
 * line isn't its own trackable shell execution -- `onDone` is not called.
 */
function runFatass(cwd, args, onDone) {
    const commandLine = fatassCommandLine(args);
    if (args[0] === "shell") {
        const t = vscode.window.createTerminal({ name: "fatass shell", cwd });
        t.show();
        runInTerminal(t, commandLine, onDone);
        return;
    }
    const t = vscode.window.activeTerminal ?? vscode.window.createTerminal({ name: "fatass", cwd });
    if (isInShellRepl(t)) {
        t.sendText(quoteArgs(args));
        return;
    }
    runInTerminal(t, commandLine, onDone);
}
