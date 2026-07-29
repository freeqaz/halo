// Ghidra script: dump every non-FUN_ function name with its address so we can
// grep for Halo's own subsystems (cache/bitmap/object/scenario/...) rather than
// just XDK library classes.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;

public class DumpFuncs extends GhidraScript {
	@Override
	public void run() throws Exception {
		StringBuilder sb = new StringBuilder();
		FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
		while (it.hasNext()) {
			Function f = it.next();
			if (f.getName().startsWith("FUN_")) {
				continue;
			}
			sb.append(f.getEntryPoint()).append('\t').append(f.getName()).append('\n');
		}
		java.nio.file.Files.writeString(java.nio.file.Path.of("/tmp/claude/pdbtest/names.txt"),
			sb.toString());
		println("RESULT wrote /tmp/claude/pdbtest/names.txt");
	}
}
