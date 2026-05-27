# Polymath-AI

<table>
<tr>
<td colspan="7" valign="top">
<sub>01 · Bento cell · b-cell b-hero cell-7 row-2</sub>
<div><span><b>00 · POLYMATH-AI</b> · MOBILE LLM TRAINING</span><span>LIVE LANE · 081431Z</span></div>
      <h1>A research lane for <span>phone-side LLM training.</span></h1>
      <p>On-device language-model training research lane &middot; Polymath-AI &middot; PyPI 0.1.0 &middot; Snapdragon 8 Elite target</p>
      <p>Polymath-AI is a training harness aimed at the <strong>Snapdragon 8 Elite (SM8750)</strong> phone chip. It trains only the first and last layers of a language model while the middle stays sealed and SHA-checked. The host smoke runs cleanly on Qwen 2.5 1.5B with the frozen middle showing <em>zero weight changes</em>. Phone compilation, licensed multilingual corpora, sustained device telemetry, and a public checkpoint are all open. This is a route, not a product.</p>
</td>
<td colspan="5" valign="top">
<sub>02 · Polymath AI animated mechanics diagram · b-cell b-codec-mechanics cell-5 row-2</sub>
<figure>
        <div><img src="docs/assets/product-page-mechanics.gif" alt="Polymath-AI approved scientific square mechanics diagram showing on-device adapter-loop mechanics."></div>
        <figcaption><b>Scope:</b> host harness and selective layer training. Phone compile, sustained telemetry, licensed corpora, and public checkpoint remain open.</figcaption>
      </figure>
</td>
</tr>
<tr>
<td colspan="4" valign="top">
<sub>03 · Bento cell · b-cell b-title cell-4</sub>
<div><b>01 · THE GAP</b><span>PHONE RUN MISSING</span></div>
      <h2>&ldquo;Training a language model on a phone still has no measured path from corpus to battery.&rdquo;</h2>
</td>
<td colspan="5" valign="top">
<sub>04 · Bento cell · b-cell b-fig cell-5</sub>
<div><b>02 · MARKETS</b><span>USER FIT</span></div>
      <div>
        <div>
          <div><span>Research infra teams</span><span></span><span>best fit</span></div>
          <div><span>Mobile runtime teams</span><span></span><span>adjacent</span></div>
          <div><span>Corpus &amp; license ops</span><span></span><span>open</span></div>
          <div><span>Production edge AI</span><span></span><span>not now</span></div>
          <div><span>Consumer apps</span><span></span><span>not now</span></div>
        </div>
      </div>
      <div>Best fit is the research-infrastructure and mobile-runtime audience deciding what to staff; no model-revenue claim is made.</div>
</td>
<td colspan="3" valign="top">
<sub>05 · Bento cell · b-cell b-stat cell-3</sub>
<div><b>03 · VALUE</b></div>
      <div><span>OPEN</span><span>NOW</span></div>
      <div>Public repo and PyPI exist; <b>the value is the training harness and its constraints, not a phone-trained model.</b></div>
</td>
</tr>
<tr>
<td colspan="3" valign="top">
<sub>06 · Bento cell · b-cell b-title is-centered cell-3</sub>
<div><b>04 · INSIGHT</b></div>
      <h2>A training harness, not a finished <span>model.</span></h2>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>07 · Bento cell · b-cell b-prose is-technical b-tech-panel</sub>
<div><b>05.0 · CURRENT TECH</b><span>HOST, CPU, NATIVE</span></div>
        <p>Mobile language-model work usually means inference on the chip, with training kept in the cloud. The conventional route ships a trained model down to the device and never lets it learn there.</p>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>08 · Bento cell · b-cell b-prose is-technical b-tech-panel</sub>
<div><b>05.1 · OUR TECH</b><span>SELECTIVE LAYER TRAINING</span></div>
        <p>Polymath trains only the boundary layers of a language model &mdash; layer 0, the final layer, and the language-model head &mdash; while every middle layer stays sealed and SHA-checked at <strong>frozen_changes = 0</strong>. Host smoke passes on <strong>Qwen 2.5 1.5B</strong>, with loss falling from <strong>14.515 to 4.449 in five steps</strong> and the middle bit-identical across the run.</p>
</td>
</tr>
<tr>
<td colspan="3" valign="top">
<sub>09 · Bento cell · b-cell b-fig b-benchmark-mini cell-3</sub>
<div><b>05.2 · BENCHMARKS</b><span>HOST HARNESS</span></div>
      <div>
        <div>
          <div><span>Host tests</span><b>PASS</b><small>reported host</small></div>
          <div><span>Smoke base</span><b>Qwen 2.5</b><small>1.5B params</small></div>
          <div><span>Checks</span><b>19</b><small>listed</small></div>
          <div><span>SoC</span><b>SM8750</b><small>SD 8 Elite resolved</small></div>
        </div>
        <div>
          <div><span>Host harness</span><span></span><span>pass</span></div>
          <div><span>Frozen middle</span><span></span><span>0 changes</span></div>
          <div><span>Phone compile</span><span></span><span>unsupported</span></div>
        </div>
      </div>
      <div><b>Device status:</b> five SM8750 phone-compile rows currently measured unsupported; host harness passes.</div>
</td>
<td colspan="4" valign="top">
<sub>10 · Bento cell · b-cell b-title cell-4</sub>
<div><b>06 · MEASUREMENT</b><span>HOST ELO SMOKE</span></div>
      <h2>Host smoke passes, phone compile remains <span>unsupported.</span></h2>
</td>
</tr>
<tr>
<td colspan="8" valign="top">
<sub>11 · Bento cell · b-cell b-fig cell-8</sub>
<div><b>06.1 · COMPARATIVE PERFORMANCE &middot; HOST VS DEVICE STATUS</b></div>
      <div>
        <div>
          <div><span>Host harness</span><span></span><span>reported pass</span></div>
          <div><span>QNN/LiteRT compile</span><span></span><span>unsupported</span></div>
          <div><span>Device telemetry</span><span></span><span>open</span></div>
          <div><span>Licensed corpus</span><span></span><span>open</span></div>
        </div>
      </div>
      <div>Host smoke &middot; <b>Qwen 2.5 1.5B, 5 training steps, loss 14.515 to 4.449</b>, frozen middle unchanged. Phone compile, licensed corpus ingestion, and sustained device telemetry are not yet measured.</div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>12 · Bento cell · b-cell b-row-label cell-12</sub>
<div><b>07 · KEY METRICS</b><span>POLYMATH-AI HOST HARNESS &middot; PYPI 0.1.0 STALE</span></div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>13 · Bento cell · b-cell b-stat</sub>
<div><b>07.1 · HOST TEST SURFACE</b></div>
      <div>PASS</div>
      <div>Host harness pass &middot; <b>reported on developer machine</b></div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>14 · Bento cell · b-cell b-stat</sub>
<div><b>07.2 · SMOKE BASE</b></div>
      <div>Qwen 2.5<span>&middot;1.5B</span></div>
      <div>Smoke base model &middot; <b>frozen_changes = 0</b></div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>15 · Bento cell · b-cell b-stat</sub>
<div><b>07.3 · CHECK ROWS</b></div>
      <div>19</div>
      <div>Listed status rows &middot; <b>documentation coverage</b></div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>16 · Bento cell · b-cell b-stat</sub>
<div><b>07.4 · TARGET SOC</b></div>
      <div>SD 8 Elite<span>&middot;open</span></div>
      <div>SM8750 resolved &middot; <b>phone compile blocked</b></div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>17 · Bento cell · b-cell b-stat</sub>
<div><b>07.5 · ON-DEVICE THROUGHPUT</b></div>
      <div>null</div>
      <div>Metric absent &middot; <b>device path unsupported</b></div>
</td>
</tr>
<tr>
<td colspan="4" valign="top">
<sub>18 · Bento cell · b-cell b-title is-centered cell-4</sub>
<div><b>08 · DETERMINISM</b><span>FROZEN MIDDLE · SHA-CHECKED</span></div>
      <h2>Frozen middle stays bit-stable while boundary layers <span>train.</span></h2>
</td>
<td colspan="5" valign="top">
<sub>19 · Bento cell · b-cell b-prose is-technical cell-5</sub>
<div><b>08.1 · WHAT DETERMINISTIC MEANS</b><span>FROZEN_CHANGES = 0</span></div>
      <p>Only the named boundary layers receive gradient updates &mdash; layer 0, the final layer, and the language-model head. The middle layers' weights are <strong>SHA-checked before and after every training pass</strong>; if any frozen weight moves, the run halts immediately and reports the offending tensor.</p>
      <p>The unit of bit-exactness is <em>per-pass, host-side</em>. Five steps on Qwen 2.5 1.5B leave the frozen middle unchanged across the entire run. No on-device determinism claim is made yet; the Qualcomm Neural Network and LiteRT paths are not exercised.</p>
</td>
<td colspan="3" valign="top">
<sub>20 · Bento cell · b-cell b-blocker cell-3</sub>
<div><b>08.2 · THE FIDELITY GAP</b></div>
      <span>Honest Blocker &middot;</span>
      <p><em>QNN/LiteRT compile</em> on the Snapdragon 8 Elite is measured unsupported, so the scheduler cannot reach the device yet. On-device execution, sustained telemetry, licensed-corpus ingestion, and the next PyPI release all remain open. Tokenization currently bloats <strong>Zulu 2.68&times;</strong> and <strong>Greek 4.38&times;</strong> past target. No phone-trained model or public checkpoint exists.</p>
</td>
</tr>
<tr>
<td colspan="4" valign="top">
<sub>21 · Bento cell · b-cell b-title cell-4</sub>
<div><b>09</b></div>
      <h2>FIVE PATHS FROM ONE <span>PHONE-SIDE TRAINING LOOP.</span></h2>
</td>
<td colspan="4" valign="top">
<sub>22 · Bento cell · b-cell b-prose cell-4</sub>
<div><b>09.1 · THIS REPO'S AMBITION</b></div>
      <p>The hinge is selective continual pretraining under real mobile constraints. Polymath-AI does not promise a finished model. It builds the scheduler, corpus discipline, and frozen-middle guarantee needed to answer one question honestly &mdash; whether training a useful language model on a phone, under battery and thermal limits, is worth doing at all.</p>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>23 · Bento cell · b-cell b-title b-statement-card</sub>
<div><b>09.2 · WHAT WORKS NOW</b></div>
        <h2>Working now: host training harness on Qwen 2.5 1.5B, frozen-middle SHA-check, scheduler framing, and a resolved chip target.</h2>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>24 · Bento cell · b-cell b-title b-statement-card</sub>
<div><b>09.3 · WHAT'S STILL OPEN</b></div>
        <h2>Still open: phone compile path, sustained device telemetry, licensed multilingual corpora, and a published checkpoint with release evidence.</h2>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>25 · Bento cell · b-cell b-unlock</sub>
<div><b>09.4</b> &middot; ADAPTATION · NEAR-TERM (12&ndash;24 MO)</div>
      <div>The fine-tune leaves the data centre</div><div>A mobile-runtime engineer who can land a boundary-layer training pass on a flagship chip stops needing a remote fine-tune to personalise a model. Adaptation becomes a battery decision on the device, not a procurement decision with a cloud vendor.</div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>26 · Bento cell · b-cell b-unlock</sub>
<div><b>09.5</b> &middot; CORPUS CUSTODY · NEAR-TERM (12&ndash;24 MO)</div>
      <div>Multilingual data stops travelling</div><div>When the training step runs on the handset, the multilingual text a model learns from no longer has to leave the phone. A speaker of an underrepresented language can contribute to their own model without their words crossing a corporate boundary.</div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>27 · Bento cell · b-cell b-unlock</sub>
<div><b>09.6</b> &middot; PERSONAL MODELS · MID-TERM (24&ndash;48 MO)</div>
      <div>One model, one person, one phone</div><div>If selective training holds at scale, a model can drift toward the person carrying it rather than the average of millions of strangers. The phone becomes a place where a small, personal model improves over months instead of being replaced quarterly.</div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>28 · Bento cell · b-cell b-unlock</sub>
<div><b>09.7</b> &middot; RECEIPTS · MID-TERM (24&ndash;48 MO)</div>
      <div>Mobile training answers to evidence</div><div>A regulator or platform reviewer who asks how an on-device model changed can be answered with a record &mdash; layer touched, update size, battery cost, quality movement &mdash; rather than a marketing claim. Phone training becomes something assessable, not just demonstrated.</div>
</td>
</tr>
<tr>
<td colspan="12" valign="top">
<sub>29 · Bento cell · b-cell b-unlock</sub>
<div><b>09.8</b> &middot; LOCAL AGENCY · PARADIGM (48 MO+)</div>
      <div>The phone becomes a knowledge instrument</div><div>Once training, telemetry, and corpus custody all fit inside the device, the phone stops being the last mile of someone else's model. It becomes a bounded place where a person's language, history, and tasks shape what their model knows.</div>
</td>
</tr>
</table>
