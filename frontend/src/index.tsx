import * as React from "react";
import * as ReactDOM from "react-dom";
import { Foo } from "./foo";

const Root: React.FC = (_props: {}) => {
	return <><h1>Hello world</h1><Foo text="Hello" /></>;
}

(window as any).initShiftplanner = (root: HTMLDivElement) => {
	ReactDOM.render(<Root />, root);
};