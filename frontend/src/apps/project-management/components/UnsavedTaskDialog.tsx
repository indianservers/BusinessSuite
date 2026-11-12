import {AlertDialog,AlertDialogContent,AlertDialogHeader,AlertDialogTitle,AlertDialogDescription,AlertDialogFooter,AlertDialogCancel,AlertDialogAction} from "@/components/ui/alert-dialog";

export default function UnsavedTaskDialog({onDiscard,onKeep,abovePopover=false,description="Your unsaved fields, failed updates and comment draft will be discarded if you leave. Changes already saved will stay saved."}:{onDiscard:(()=>void)|null;onKeep:()=>void;abovePopover?:boolean;description?:string}){
 return <AlertDialog open={!!onDiscard} onOpenChange={open=>{if(!open)onKeep();}}><AlertDialogContent className={abovePopover?"z-[1101]":"z-[91]"} overlayClassName={abovePopover?"z-[1100]":"z-[90]"}>
  <AlertDialogHeader><AlertDialogTitle>Keep your unsaved task work?</AlertDialogTitle><AlertDialogDescription>{description}</AlertDialogDescription></AlertDialogHeader>
  <AlertDialogFooter><AlertDialogCancel onClick={onKeep}>Keep editing</AlertDialogCancel><AlertDialogAction onClick={()=>onDiscard?.()}>Discard changes and leave</AlertDialogAction></AlertDialogFooter>
 </AlertDialogContent></AlertDialog>;
}
