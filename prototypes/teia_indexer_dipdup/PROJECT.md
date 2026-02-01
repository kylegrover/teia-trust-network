Contract Master Schema

Here is the "Mental Map" of the contracts you are indexing. Keep this handy for your Trust Engine logic.
Contract	DipDup Name	Entrypoint	Input Shape (Python)	What it means
HEN V2	hen_v2	collect	parameter.root (int)	"I am buying Swap #root"
Teia	teia_market	collect	parameter.root (int)	"I am buying Swap #root"
HEN V2	hen_v2	swap	objkt_id, xtz_per_objkt	"I am listing Token #objkt_id"
Teia	teia_market	swap	objkt_id, xtz_per_objkt	"I am listing Token #objkt_id"

see schema_sniffer_out.txt for full schema

