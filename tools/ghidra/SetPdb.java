// Ghidra prescript: point the PDB Universal analyzer at an explicit PDB file
// and allow the untrusted (non-symbol-server) path. Run via analyzeHeadless
// -preScript SetPdb.java <pdb-path>
import ghidra.app.script.GhidraScript;
import ghidra.app.plugin.core.analysis.PdbUniversalAnalyzer;
import java.io.File;

public class SetPdb extends GhidraScript {
	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		File pdb = new File(args[0]);
		println("SetPdb: " + pdb + " exists=" + pdb.exists());
		PdbUniversalAnalyzer.setAllowUntrustedOption(currentProgram, true);
		PdbUniversalAnalyzer.setPdbFileOption(currentProgram, pdb);
	}
}
