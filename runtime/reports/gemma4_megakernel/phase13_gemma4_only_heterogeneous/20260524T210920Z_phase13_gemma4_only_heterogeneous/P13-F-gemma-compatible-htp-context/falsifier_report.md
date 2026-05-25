# P13-F Falsifier Report

- Gemma compatibility requires `google/gemma-4-E4B`, hidden size `2560`, and an input tensor sliced from the Gemma4 megakernel layer0 reference output.
- Qwen/random-init hidden-size-1536 artifacts are not used for context generation, input, execution, or promotion.
- HTP promotion requires phone `qnn-context-binary-generator` plus phone `qnn-net-run` success. Tool help alone is not accepted.
- The selected HTP island is not treated as HTP backprop, updateable QNN training, or integrated heterogeneous learning.
