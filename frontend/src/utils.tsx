import * as React from "react";

export const StringEdit: React.FC<{
	state: [string, (v: string) => void],
	save: () => void,
	onCancel?: () => void,
	placeholder?: string,
	multiline?: boolean,
	style?: React.CSSProperties,
	className?: string,
	inputRef?: React.LegacyRef<HTMLInputElement>,
}> = (props) => {
	const lineCount = props.state[0].split("\n").length;
	if (props.multiline) return <textarea
		value={props.state[0]}
		onChange={(e) => props.state[1](e.target.value)}
		placeholder={props.placeholder}
		style={{font: "inherit", flex: "1 0 auto"}}
		rows={lineCount}
	/>;
	const onKeyDown = props.onCancel == null ? undefined : (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.code === "Escape" && props.onCancel != null) props.onCancel();
	}
	const onKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.code !== "Enter") return;
		e.preventDefault();
		props.save();
	};
	return <input
		value={props.state[0]}
		onChange={(e) => props.state[1](e.target.value)}
		onKeyPress={onKeyPress}
		onKeyDown={onKeyDown}
		placeholder={props.placeholder}
		style={{flex: "1 0 auto", ...(props.style || {})}}
		className={props.className}
		ref={props.inputRef}
	/>;
}

export const UncontrolledStringEdit: React.FC<{
	value: string,
	onSave: (s: string) => void,
	onCancel?: () => void,
	style?: React.CSSProperties,
	className?: string,
	inputRef?: React.LegacyRef<HTMLInputElement>,
}> = ({value, onSave, onCancel, style, className, inputRef}) => {
	const state = React.useState(value);
	const dirty = value !== state[0];
	return <StringEdit
		state={state}
		save={() => onSave(state[0])}
		onCancel={onCancel}
		style={{...style, background: dirty ? "white" : "transparent"}}
		className={className}
		inputRef={inputRef}
		/>;
};

export const useEditables = (initials: string[]) => {
	const editors: [string, React.Dispatch<React.SetStateAction<string>>][] = [];
	let edited = false;
	for (const i of initials) {
		editors.push(React.useState(i));
		if (editors[editors.length - 1][0] !== i) edited = true;
	}
	const values = editors.map(([v]) => v);
	return [edited, values, editors] as [boolean, typeof values, typeof editors];
}

export const useReorderableList = (onReorder: (i: number, j: number) => void) => {
	const [currentDropTarget, setCurrentDropTarget] = React.useState<number | null>(null);
	const [dragging, setDragging] = React.useState<number | null>(null);
	return {
		onDragLeave: (i: number) =>
			(_e: React.DragEvent) =>
				setCurrentDropTarget((v) => v === i ? null : v),
		onDragEnter: (i: number) =>
			(_e: React.DragEvent) => setCurrentDropTarget(i),
		onDragOver: (_i: number) =>
			(e: React.DragEvent) => {if (dragging != null) e.preventDefault();},
		onDrop: (i: number) =>
			(e: React.DragEvent) => {
				if (dragging == null || currentDropTarget !== i) return;
				e.preventDefault();
				onReorder(dragging, currentDropTarget);
			},
		isDragging: (i: number) => (dragging != null && currentDropTarget === i),
		onDragStart: (i: number) => (_e: React.DragEvent) => setDragging(i),
		onDragEnd: (i: number) => (_e: React.DragEvent) => setDragging((v) => v === i ? null : v),
	}
};

/// Move xs[i] to before xs[j] without modifying the list reference xs.
/// Returns a new list IF AND ONLY IF the elements are reordered.
/// Otherwise, returns the original list reference.
export const reorderList = <T extends any>(xs: T[], i: number, j: number) => {
	if (i === j || i + 1 === j) return xs;
	const newList = [...xs];
	newList.splice(i, 1);
	newList.splice(j < i ? j : (j - 1), 0, xs[i]);
	return newList;
}
