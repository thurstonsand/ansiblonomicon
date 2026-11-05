import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import type { PluginAPI } from '@ampcode/plugin'

export const description =
	'Rejects newly added full-line comments that narrate the editing conversation; allows comments about current behavior and rationale.'

const pattern =
	/^\s*(?:\/\/|#|\/\*|\*|<!--).*\b(?:changed from|used to be|previously (?:this|it)|as (?:you )?requested)\b/i

export default function noChatComments(amp: PluginAPI) {
	amp.on('tool.call', async (event, ctx) => {
		const input = event.input
		let lines: string[]
		if (event.tool === 'apply_patch' && typeof input.patchText === 'string') {
			lines = input.patchText
				.split(/\r?\n/)
				.filter((line) => line.startsWith('+'))
				.map((line) => line.slice(1))
		} else if (
			event.tool === 'edit_file' &&
			typeof input.new_str === 'string' &&
			typeof input.old_str === 'string'
		) {
			const previous = new Set(input.old_str.split(/\r?\n/))
			lines = input.new_str.split(/\r?\n/).filter((line) => !previous.has(line))
		} else if (
			event.tool === 'create_file' &&
			typeof input.content === 'string' &&
			typeof input.path === 'string'
		) {
			const root = ctx.system.workspaceRoot
			if (!root) return { action: 'allow' }
			let before: string
			try {
				before = await readFile(
					resolve(amp.helpers.filePathFromURI(root), input.path),
					'utf8',
				)
			} catch (error) {
				if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
				before = ''
			}
			const previous = new Set(before.split(/\r?\n/))
			lines = input.content.split(/\r?\n/).filter((line) => !previous.has(line))
		} else {
			return { action: 'allow' }
		}
		if (lines.some((line) => pattern.test(line))) {
			return {
				action: 'reject-and-continue',
				message:
					'Write comments for the code, not the chat. Explain current behavior and rationale; remove conversation or edit-history narration from the new comment.',
			}
		}
		return { action: 'allow' }
	})
}
