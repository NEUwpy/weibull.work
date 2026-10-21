"""用可编辑曲线、样本表示、网络与反馈图像解释两条推断路线。"""
from pathlib import Path
import math
from 细图绘制 import Diagram

ROOT=Path(__file__).resolve().parent
PURPLE, BLUE, GREEN, ORANGE='#785499','#2D6D91','#347B68','#AE6C25'


def chart(d,key,x,y,w,h,xlabel,ylabel):
    d.line(key+'-x',[(x,y+h),(x+w,y+h)],color='#8090A0',arrow='block')
    d.line(key+'-y',[(x,y+h),(x,y)],color='#8090A0',arrow='block')
    d.text(key+'-xl',xlabel,x+w-220,y+h+8,225,38,size=22,align='right')
    d.text(key+'-yl',ylabel,x-5,y-43,w,40,size=22)


def curve(d,key,values,x,y,w,h,color):
    maximum=max(values)
    points=[(x+i*w/(len(values)-1),y+h-v/maximum*h) for i,v in enumerate(values)]
    d.line(key,points,color=color,width=4)
    return points


def base(key,title,subtitle):
    d=Diagram(key,title,2000,1090)
    d.text('title',title,45,20,1910,65,size=35,bold=True)
    d.text('subtitle',subtitle,45,95,1910,55,size=26)
    for i,x in enumerate([45,720,1395],1):d.panel(f'step-{i}',x,180,560,590,fill='#F8F9FC')
    for i in [1,2]:d.edge(f'flow-{i}',f'step-{i}',f'step-{i+1}',color='#617487',width=3.5)
    return d


def posterior():
    d=base('posterior-information-flow','后验推断｜把样本支持与已有信息合在一起，再按后验规则作判断',
           '先看哪些参数受到支持，再看后验权重如何变化，最后说明为什么选择某个估计。')
    d.text('s1','① 看样本支持与先验信息',65,200,520,55,size=29,bold=True)
    d.text('s2','② 相乘并归一化为后验',740,200,520,55,size=29,bold=True)
    d.text('s3','③ 按后验规则确定估计',1415,200,520,55,size=29,bold=True)
    xx=[.03+.97*i/100 for i in range(101)]
    like=[math.exp(-.5*(math.log(v/.39)/.48)**2)/v for v in xx]
    prior=[.35+math.exp(-.5*((v-.62)/.33)**2) for v in xx]
    post=[a*b for a,b in zip(like,prior)]
    mean=sum(x*p for x,p in zip(xx,post))/sum(post)
    variance=sum(p*(x-mean)**2 for x,p in zip(xx,post))/sum(post)
    chart(d,'support',110,340,430,230,'候选参数值','相对支持程度')
    curve(d,'likelihood',like,110,340,430,230,BLUE)
    curve(d,'prior',prior,110,340,430,230,PURPLE)
    d.line('blue-legend',[(100,635),(145,635)],color=BLUE,width=4)
    d.text('like-label','样本似然：观测更支持哪里',155,613,410,44,size=24)
    d.line('purple-legend',[(100,690),(145,690)],color=PURPLE,width=4)
    d.text('prior-label','参数先验：已有信息支持哪里',155,668,410,44,size=24)
    chart(d,'post',785,340,430,230,'候选参数值','后验密度')
    maximum=max(post)
    for i in range(0,len(post),3):
        height=post[i]/maximum*220
        d.box('area-'+str(i),'',785+i*430/100,570-height,8,height,fill='#E9DDF3',color='none',role='background')
    curve(d,'posterior',post,785,340,430,230,PURPLE)
    d.text('multiply','后验 ∝ 似然 × 先验',755,620,490,50,size=29,bold=True,align='center')
    d.text('uncertainty','曲线保留参数的不确定性',755,685,490,42,size=25,align='center')
    chart(d,'risk',1460,340,430,230,'候选估计 a','后验平均损失')
    risks=[(v-mean)**2+variance for v in xx]
    curve(d,'average-risk',risks,1460,340,430,230,GREEN)
    px=1460+(mean-.03)/.97*430
    py=570-variance/max(risks)*230
    d.line('chosen-guide',[(px,570),(px,py)],color=GREEN,dashed=True)
    d.box('chosen','',px-7,py-7,14,14,fill=GREEN,color=GREEN)
    d.text('risk-rule','例如：平方损失下，取后验均值',1415,620,520,50,size=25,bold=True,align='center')
    d.text('other-rules','中位数或MAP使用各自的后验规则',1415,685,520,42,size=24,align='center')
    d.text('schematic','曲线为原理示意：图中用一维参数说明；三参数问题形成β、η、γ的联合后验。',55,810,1890,50,size=24)
    for i,(x,text) in enumerate([(45,'① 先验范围与权重'),(720,'② 后验计算与近似'),(1395,'③ 损失函数与估计规则')]):
        d.box('change-'+str(i),text,x,925,560,85,color=PURPLE,fill='#F5EDF9',size=26)
    d.text('changes','比较方法时，沿上述编号定位其改变的环节。',55,1025,1890,42,size=24)
    d.save(ROOT/'10-后验推断路线-信息处理流程.drawio')


def learning():
    d=base('learning-information-flow','学习映射｜从样本特征学习参数预测，用真值误差反复调整映射',
           '训练判据来自多组样本及其参数标签；训练完成后，固定估计函数供新样本使用。')
    d.text('s1','① 把样本整理为特征',65,200,520,55,size=29,bold=True)
    d.text('s2','② 用映射预测并对照真值',740,200,520,55,size=29,bold=True)
    d.text('s3','③ 汇总误差、更新权重',1415,200,520,55,size=29,bold=True)
    chart(d,'features',110,340,430,230,'排序位置／特征维度','一组样本的特征')
    vals=[.12,.18,.23,.30,.36,.43,.52,.64,.80,.96]
    for i,v in enumerate(vals):
        d.box('feature-'+str(i),'',125+i*39,570-v*205,21,v*205,color=BLUE,fill='#A9C9DD')
    d.text('feature-mapping','排序值、分位数或统计量',75,620,500,50,size=27,bold=True,align='center')
    d.text('feature-consistency','各组样本沿用同一种表示 T(D)',75,685,500,42,size=24,align='center')
    layers=[[(795,340),(795,415),(795,490)],[(970,315),(970,380),(970,445),(970,510)],[(1145,340),(1145,415),(1145,490)]]
    for layer in range(2):
        for i,a in enumerate(layers[layer]):
            for j,b in enumerate(layers[layer+1]):d.line(f'connection-{layer}-{i}-{j}',[a,b],color='#CBB69C',width=1.6)
    for layer,centers in enumerate(layers):
        for i,(cx,cy) in enumerate(centers):
            circle=[(cx+15*math.cos(2*math.pi*k/24),cy+15*math.sin(2*math.pi*k/24)) for k in range(25)]
            d.line(f'neuron-{layer}-{i}',circle,color=ORANGE,width=3)
    d.text('feature-network','特征',765,535,100,38,size=23,align='center')
    d.text('weights-network','可训练权重 φ',880,535,210,38,size=23,align='center')
    d.text('output-network','参数预测',1090,535,135,38,size=23,align='center')
    for i,(label,true,pred) in enumerate([('β',57,42),('η',75,61),('γ',48,66)]):
        x=815+145*i
        d.box('true-'+str(i),'',x,660-true,24,true,fill='#93A0AC',color='none')
        d.box('pred-'+str(i),'',x+31,660-pred,24,pred,fill='#C99144',color='none')
        d.text('parameter-'+str(i),label,x-5,668,75,38,size=25,align='center')
    d.text('compare','灰：参数真值　橙：预测（尺度化示意）',745,715,510,40,size=22,align='center')
    chart(d,'loss',1460,340,430,230,'权重更新次数','规定的预测损失')
    values=[.78*math.exp(-i/25)+.1+.025*math.sin(i*.32) for i in range(101)]
    curve(d,'training-loss',values,1460,340,430,230,ORANGE)
    d.text('objective','使多组参数预测的规定损失更小',1415,620,520,50,size=26,bold=True,align='center')
    d.text('loss-formula','φ* = argminφ 平均ⱼ损失(预测ⱼ,真值ⱼ)',1415,685,520,42,size=24,align='center')
    d.edge('update-cycle','step-3','step-2','更新共享映射，再预测与比较',color=ORANGE,kind='feedback',start='bottom',end='bottom',via=[(1675,815),(1000,815)],at=(1350,815))
    d.text('schematic','网络、特征柱与训练曲线为原理示意；灰／橙柱用于说明逐参数误差的形成。',55,865,1890,40,size=23)
    for i,(x,text) in enumerate([(45,'① 特征与训练样本范围'),(720,'② 映射结构与过程量'),(1395,'③ 损失、训练与校准')]):
        d.box('change-'+str(i),text,x,935,560,70,color=ORANGE,fill='#FCF3E6',size=26)
    d.text('deployment','训练结束后固定φ*：新样本的T(D)进入同一映射，得到参数估计。',55,1025,1890,42,size=24)
    d.save(ROOT/'11-学习映射路线-信息处理流程.drawio')


if __name__=='__main__':
    posterior();learning()
    print('generated visual posterior and learning flows')
