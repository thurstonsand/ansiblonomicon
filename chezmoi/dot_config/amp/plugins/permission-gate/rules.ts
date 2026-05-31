import type { PermissionSubject } from "./subjects.ts";

export type PermissionRule = {
	toolNames: readonly string[];
	label: string;
	description: string;
	matches: (subject: PermissionSubject) => boolean;
};

export type PermissionMatch = {
	subject: PermissionSubject;
	rule: PermissionRule;
};

function commandRule(
	label: string,
	description: string,
	matches: (command: string) => boolean,
): PermissionRule {
	return {
		toolNames: ["shell"],
		label,
		description,
		matches: (subject) =>
			subject.kind === "shell-command" && matches(subject.command),
	};
}

function commandPatternRule(
	label: string,
	description: string,
	pattern: RegExp,
): PermissionRule {
	return commandRule(label, description, (command) => pattern.test(command));
}

function stripOuterQuotes(token: string): string {
	if (token.length < 2) return token;

	const first = token[0];
	const last = token[token.length - 1];

	return first === last && (first === '"' || first === "'")
		? token.slice(1, -1)
		: token;
}

function tokenizeShellWords(command: string): string[] {
	return command.match(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\S+/g) ?? [];
}

export function isRecursiveForcedRemovalCommand(command: string): boolean {
	const segments = command.split(/&&|\|\||;|\n/);

	for (const segment of segments) {
		const tokens = tokenizeShellWords(segment).map(stripOuterQuotes);

		for (let index = 0; index < tokens.length; index++) {
			if (tokens[index] !== "rm") continue;

			let hasRecursive = false;
			let hasForce = false;

			for (
				let optionIndex = index + 1;
				optionIndex < tokens.length;
				optionIndex++
			) {
				const token = tokens[optionIndex];

				if (token === "--") break;
				if (!token.startsWith("-") || token === "-") break;

				if (token.startsWith("--")) {
					hasRecursive ||= token === "--recursive";
					hasForce ||= token === "--force";
					continue;
				}

				const flags = token.slice(1);
				hasRecursive ||= flags.includes("r");
				hasForce ||= flags.includes("f");
			}

			if (hasRecursive && hasForce) return true;
		}
	}

	return false;
}

export const PERMISSION_RULES: PermissionRule[] = [
	commandPatternRule(
		"git mutation",
		"git stash/add/commit/push/checkout/reset/clean/rebase",
		/\bgit\s+(\S+\s+)*?(stash|add|commit|push|checkout|reset|clean|rebase)\b/i,
	),
	commandRule(
		"recursive forced removal",
		"rm with both recursive (-r/--recursive) and force (-f/--force) flags",
		isRecursiveForcedRemovalCommand,
	),
	commandPatternRule(
		"destructive find",
		"find with -delete",
		/find\s+.*-delete/i,
	),
];

export function findMatchingRule(
	subject: PermissionSubject,
): PermissionMatch | undefined {
	const rule = PERMISSION_RULES.find((candidate) => candidate.matches(subject));
	return rule ? { subject, rule } : undefined;
}
