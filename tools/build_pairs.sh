#!/bin/bash
# Builds the eng-spa and es-pt (pt_BR) pairs from source (~/apertium-win/src) with the Windows build's .exe
# (the final executable uses these same programs). Text steps (xsltproc, filters) run on Linux.
set -e
W=~/apertium-win; B=$W/bin; OUT=$W/data2; X=~/apertium-local/root/usr
export LD_LIBRARY_PATH=$X/lib/x86_64-linux-gnu PATH=$X/bin:$B:$PATH
w() { wslpath -w "$1"; }
exe() { local p=$1; shift; local a=(); for x in "$@"; do if [ -e "$x" ] || [ -d "$(dirname "$x")" ] && [[ $x == /* ]]; then a+=("$(w "$x")"); else a+=("$x"); fi; done; "$B/$p.exe" "${a[@]}"; }
mkdir -p $OUT
S=$W/src/apertium-en-es; cd $S; mkdir -p .deps; N=apertium-eng-spa
xsltproc --stringparam alt eng_GB alt.xsl $N.eng.metadix > .deps/eng.metadix
xsltproc buscaPar.xsl .deps/eng.metadix | uniq > tmp1.xsl && xsltproc tmp1.xsl .deps/eng.metadix > .deps/eng.dix && rm tmp1.xsl
exe lt-comp lr $S/.deps/eng.dix $OUT/eng-spa.automorf.bin $S/$N.eng.acx
exe lt-comp lr $S/$N.eng-spa.dix $OUT/eng-spa.autobil.bin
exe lt-comp rl $S/$N.spa.dix $OUT/eng-spa.autogen.bin
exe lt-comp lr $S/$N.post-spa.dix $OUT/eng-spa.autopgen.bin
exe lrx-comp $S/$N.eng-spa.lrx $OUT/eng-spa.autolex.bin
for t in genitive.t1x t1x t2x t3x; do cp $S/$N.eng-spa.$t $OUT/; exe apertium-preprocess-transfer $OUT/$N.eng-spa.$t $OUT/eng-spa.${t%.t1x}.bin; done
mv $OUT/eng-spa.genitive.bin $OUT/eng-spa.genitive.bin 2>/dev/null || true
cp $S/eng-spa.prob $OUT/
S=$W/src/apertium-es-pt; cd $S; N=apertium-es-pt
# Brazilian variant through lt-comp itself (the old xslt filter produced a dictionary that did not match)
apertium-filter-rules pt_BR $N.es-pt.t1x > $OUT/es-pt_BR.t1x
exe lt-comp lr $S/$N.es.dix $OUT/es-pt.automorf.bin
exe lt-comp -r br lr $S/$N.es-pt.dix $OUT/es-pt_BR.autobil.bin
exe lt-comp -v br rl $S/$N.pt.dix $OUT/es-pt_BR.autogen.bin
exe lt-comp -v br lr $S/$N.post-pt.dix $OUT/es-pt_BR.autopgen.bin
exe apertium-preprocess-transfer $OUT/es-pt_BR.t1x $OUT/es-pt_BR.t1x.bin
# European variant (pt_PT)
apertium-filter-rules pt_PT $N.es-pt.t1x > $OUT/es-pt_PT.t1x
exe lt-comp -r pt lr $S/$N.es-pt.dix $OUT/es-pt_PT.autobil.bin
exe lt-comp -v pt rl $S/$N.pt.dix $OUT/es-pt_PT.autogen.bin
exe lt-comp -v pt lr $S/$N.post-pt.dix $OUT/es-pt_PT.autopgen.bin
exe apertium-preprocess-transfer $OUT/es-pt_PT.t1x $OUT/es-pt_PT.t1x.bin
cp $S/es-pt.prob $OUT/
# French -> Spanish (then the es-pt pair): French games
S=$W/src/apertium-fr-es; cd $S; mkdir -p .deps; N=apertium-fra-spa
am() { gawk '{gsub("&", "&amp;"); print;}'; }
xsltproc buscaPar.xsl $N.fra.metadix | am | uniq > tmp1.xsl && xsltproc tmp1.xsl $N.fra.metadix | am > .deps/fra-full.dix && rm tmp1.xsl
xsltproc --stringparam alt std alt.xsl .deps/fra-full.dix | am > .deps/fra.dix
xsltproc --stringparam alt std alt.xsl $N.spa.dix | am > .deps/spa.dix
xsltproc translate-to-default-equivalent.xsl $N.fra-spa.dix | am > .deps/common.dix
xsltproc --stringparam alt std alt.xsl .deps/common.dix | am > .deps/fra-spa.dix
exe lt-comp lr $S/.deps/fra.dix $OUT/fra-spa.automorf.bin $S/$N.fra.acx
exe lt-comp lr $S/.deps/fra-spa.dix $OUT/fra-spa.autobil.bin
exe lt-comp rl $S/.deps/spa.dix $OUT/fra-spa.autogen.bin $S/$N.spa.acx
exe lt-comp lr $S/$N.post-spa.dix $OUT/fra-spa.autopgen.bin
exe lrx-comp $S/$N.fra-spa.lrx $OUT/fra-spa.autolex.bin
for t in t1x t2x t3x; do cp $S/$N.fra-spa.$t $OUT/; exe apertium-preprocess-transfer $OUT/$N.fra-spa.$t $OUT/fra-spa.$t.bin; done
cp $S/fra-spa.prob $OUT/
ls -la $OUT
