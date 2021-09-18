import * as React from "react";

export const Foo: React.FC = (props: {text: string}) => {
	return <ul><li>{props.text}</li></ul>;
}