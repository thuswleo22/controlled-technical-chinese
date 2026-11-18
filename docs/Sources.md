# 来源与许可证

项目原创材料见 [MIT 许可证](../LICENSE)。研究中引用的第三方文档按其上游许可使用。以下固定版本用于采集中文技术语料。原始快照及其段落由用户从上游生成。

| 上游与作者 | 固定版本 | 文档许可 |
| --- | --- | --- |
| Kubernetes 文档贡献者 | [47132eb](https://github.com/kubernetes/website/tree/47132eb5367cfdcba0a3b33a0b3ffc81185bd7e8/content/zh-cn/docs) | [CC BY 4.0](https://github.com/kubernetes/website/blob/47132eb5367cfdcba0a3b33a0b3ffc81185bd7e8/LICENSE) |
| MDN Web Docs 贡献者 | [69242ec](https://github.com/mdn/translated-content/tree/69242ec9d69118cdfeee571ac44c5325530bfdbc/files/zh-cn) | [文档通常为 CC BY-SA 2.5 或更高版本](https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license) |
| PingCAP 与 TiDB 文档贡献者 | [5214a56](https://github.com/pingcap/docs-cn/tree/5214a56c3ea96fde99fe3bea0f0c55b02d277757) | [CC BY-SA 3.0](https://github.com/pingcap/docs-cn/blob/5214a56c3ea96fde99fe3bea0f0c55b02d277757/LICENSE) |

最初的受控写作背景见 [ASD-STE100](https://www.asd-ste100.org/)。合并前的 Carbon 草案用于评估规则设计，草案由用户提供并保存在研发目录中。[设计取舍](Design.md) 记录合并后的判断。

## 从上游采集

从仓库根目录运行，需要网络和 `curl`。快照记录上游地址、提交、SHA-256 和每段起始行。采集脚本省略代码与注释，合并正文折行。产生的快照保存在本地 `corpus/` 目录。

```sh
python3 experiments/collect_corpus.py --dataset kubernetes
python3 experiments/collect_corpus.py --dataset mdn
python3 experiments/collect_corpus.py --dataset tidb
python3 experiments/collect_corpus.py --dataset kubernetes-lexicon
python3 experiments/collect_corpus.py --dataset tidb-status
```

研究依存关系和词频时，安装 `ufal.udpipe==1.3.1.1`，下载固定版本的模型，然后运行分析器。分析器核对模型的 SHA-256。模型源自 UDPipe 2.5 (191206)，按[上游模型条款](https://ufal.mff.cuni.cz/udpipe/1/models)使用。模型和外部语料仅用于这里的研究步骤，日常检查器只需 Python。

```sh
curl -fsSL -o chinese-gsdsimp.udpipe 'https://raw.githubusercontent.com/jwijffels/udpipe.models.ud.2.5/17d6bbfb7f138f9ba2cf04692f15d892becf0246/inst/udpipe-ud-2.5-191206/chinese-gsdsimp-ud-2.5-191206.udpipe'
python3 experiments/profile_baseline.py --model chinese-gsdsimp.udpipe --corpus corpus/kubernetes_v134.json > results/kubernetes_baseline.json
python3 experiments/profile_baseline.py --model chinese-gsdsimp.udpipe --corpus corpus/mdn_external.json > results/mdn_baseline.json
python3 experiments/audit_candidate_lexicon.py --kubernetes results/kubernetes_baseline.json --mdn results/mdn_baseline.json
```
