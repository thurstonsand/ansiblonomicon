import type { PluginAPI } from '@ampcode/plugin'

export const description =
	'Adds shell timing to agent context, with warnings over 60 seconds and stronger warnings over 5 minutes.'

interface Timings {
	starts: Map<string, number>
	processes: Map<number, number>
}

export default function commandTiming(amp: PluginAPI) {
	const threads = new Map<string, Timings>()

	amp.on('tool.call', (event) => {
		if (amp.helpers.shellCommandFromToolCall(event)) {
			let timings = threads.get(event.thread.id)
			if (!timings) {
				timings = { starts: new Map(), processes: new Map() }
				threads.set(event.thread.id, timings)
			}
			timings.starts.set(event.toolUseID, performance.now())
		}
		return { action: 'allow' }
	})

	amp.on('tool.result', (event) => {
		const timings = threads.get(event.thread.id)
		if (!timings) return
		const polling =
			event.tool === 'shell_command_status' ||
			event.tool === 'shell_command_kill'
		const started =
			polling && typeof event.input.pid === 'number'
				? timings.processes.get(event.input.pid)
				: timings.starts.get(event.toolUseID)
		timings.starts.delete(event.toolUseID)
		if (started === undefined) return
		const now = performance.now()
		const seconds = (now - started) / 1000
		const output = event.output
		const object =
			output !== null && typeof output === 'object' && !Array.isArray(output)
				? (output as Record<string, unknown>)
				: undefined
		const running = object?.running === true
		if (running && typeof object?.pid === 'number') {
			timings.processes.set(object.pid, started)
		} else if (polling && typeof event.input.pid === 'number') {
			// A failed poll does not tell us whether the process finished.
			if (event.status === 'done' && object?.running === false) {
				timings.processes.delete(event.input.pid)
			} else {
				return
			}
		}
		let message = `[command-timing] Shell elapsed${running ? ' so far' : ''}: ${seconds.toFixed(1)}s (includes hook/approval wait${polling ? ' and time between polls' : ''}).`
		if (seconds > 300) {
			message +=
				' Very slow feedback loop: over 5 minutes. Change the iteration strategy before repeating this command.'
		} else if (seconds > 60) {
			message += ' Slow feedback loop: over 60 seconds.'
		}
		if (seconds > 60) {
			message +=
				" Find a narrower test, file, or reproduction for the next edit. Keep required full-suite validation for the final check; don't skip verification."
		}
		return {
			status: event.status,
			...(event.status !== 'done' ? { error: event.error } : {}),
			output: object
				? { ...object, commandTiming: message }
				: Array.isArray(output)
					? [...output, { type: 'text', text: message }]
					: `${output ?? ''}\n\n${message}`,
		}
	})
}
