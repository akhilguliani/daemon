cores=10
for fname in prop_30_70 prop_70_30 prop_50_50 prop_10_90 prop_90_10
#for fname in prio_10_0
do
    for i in 85 50 40
    do
        echo "python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=False 3 >> results/our_policy_${fname}_${i}_test"
        python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=False 3 >> results/prop/our_policy_${fname}_${i}_${cores} &
        pypid=$!
        echo $pypid
        sleep 100
        kill -INT $pypid
        sleep 5
        killall python
        killall leela_r
        killall cactusBSSN_r
        sleep 5
        
        echo "python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=True 3 >> results/rapl_policy_${fname}_${i}_test"
        python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=True 3 >> results/prop/rapl_policy_${fname}_${i}_${cores} &
        pypid=$!
        echo $pypid
        sleep 60
        kill -INT $pypid
        sleep 5
        killall python
        killall leela_r
        killall cactusBSSN_r
        sleep 5
    done
done
