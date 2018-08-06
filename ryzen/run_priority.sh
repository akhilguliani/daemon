cores=10
for fname in prio_10_0 prio_10_3 prio_10_5 prio_10_7 prio_10_9
# for fname in prio_10_7
do
    for i in 85 50 40
    do
        echo "python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=False 3 >> results/our_policy_${fname}_${i}_test"
        python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=False 3 >> results/our_policy_${fname}_${i}_${cores} &
        pypid=$!
        echo $pypid
        sleep 400
        kill -INT $pypid
        sleep 5
        killall python
        killall leela_r
        killall cactusBSSN_r
        sleep 5
        
        echo "python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=True 3 >> results/rapl_policy_${fname}_${i}_test"
        python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=True 3 >> results/rapl_policy_${fname}_${i}_${cores} &
        pypid=$!
        echo $pypid
        sleep 400
        kill -INT $pypid
        sleep 5
        killall python
        killall leela_r
        killall cactusBSSN_r
        sleep 5
    done
done
