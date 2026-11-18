import {Children,cloneElement,isValidElement,type ReactElement,type ReactNode} from "react";
import {Area,Bar,Line,ResponsiveContainer,Tooltip} from "recharts";
/** Pure presentation of an already-loaded read-only chart for the phone zoom view. */
export function expandedChartContent(chart:ReactElement):ReactElement {
 const props=chart.props as {children?:ReactNode};
 return cloneElement(chart as ReactElement<{accessibilityLayer?:boolean;children?:ReactNode}>,{accessibilityLayer:true},Children.map(props.children,child=>{
  if(!isValidElement(child))return child;
  if(child.type===Tooltip)return cloneElement(child as ReactElement<{trigger?:"hover"|"click"}>,{trigger:"click"});
  const series=child.props as {name?:string;dataKey?:unknown};
  if((child.type===Area||child.type===Bar||child.type===Line)&&!series.name&&typeof series.dataKey==='string'){
   const label=series.dataKey.replace(/_/g,' ');
   return cloneElement(child as ReactElement<{name?:string}>,{name:label.charAt(0).toUpperCase()+label.slice(1)});
  }
  return child;
 }));
}
export function expandedResponsiveChartContent(content:ReactNode):ReactNode {
 if(!isValidElement(content)||content.type!==ResponsiveContainer)return content;
 const props=content.props as {children?:ReactNode};
 return cloneElement(content as ReactElement<{width?:string|number;height?:string|number;children?:ReactNode}>,{width:'100%',height:'100%'},isValidElement(props.children)?expandedChartContent(props.children):props.children);
}
